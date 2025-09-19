-- Embedding Status Tracking Enhancement
-- This script adds tracking to ensure embeddings are generated only once

-- Add status column to product_embeddings table
ALTER TABLE public.product_embeddings
ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'pending';

-- Add generation_attempt_count to track retry attempts
ALTER TABLE public.product_embeddings
ADD COLUMN IF NOT EXISTS generation_attempts INTEGER DEFAULT 0;

-- Add last_error column to track any generation errors
ALTER TABLE public.product_embeddings
ADD COLUMN IF NOT EXISTS last_error TEXT;

-- Create index on status for efficient querying
CREATE INDEX IF NOT EXISTS idx_product_embeddings_status
ON public.product_embeddings (status);

-- Create a composite index for efficient batch processing
CREATE INDEX IF NOT EXISTS idx_product_embeddings_status_attempts
ON public.product_embeddings (status, generation_attempts);

-- Create embedding generation tracking table
CREATE TABLE IF NOT EXISTS public.embedding_generation_runs (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  completed_at TIMESTAMP WITH TIME ZONE,
  status VARCHAR(20) NOT NULL DEFAULT 'running', -- 'running', 'completed', 'failed', 'partial'
  total_products INTEGER DEFAULT 0,
  processed_products INTEGER DEFAULT 0,
  successful_embeddings INTEGER DEFAULT 0,
  failed_embeddings INTEGER DEFAULT 0,
  skipped_embeddings INTEGER DEFAULT 0,
  model_name VARCHAR(100) DEFAULT 'all-MiniLM-L6-v2',
  run_type VARCHAR(50) DEFAULT 'full_generation', -- 'full_generation', 'incremental', 'retry_failed'
  notes TEXT,
  error_details TEXT,
  CONSTRAINT embedding_generation_runs_pkey PRIMARY KEY (id)
);

-- Create index on embedding_generation_runs for efficient querying
CREATE INDEX IF NOT EXISTS idx_embedding_generation_runs_status
ON public.embedding_generation_runs (status);

CREATE INDEX IF NOT EXISTS idx_embedding_generation_runs_started_at
ON public.embedding_generation_runs (started_at DESC);

-- Function to check if embeddings are already generated for all products
CREATE OR REPLACE FUNCTION check_embeddings_completion()
RETURNS JSON
LANGUAGE SQL STABLE
AS $$
  SELECT json_build_object(
    'total_products', (SELECT COUNT(*) FROM products),
    'products_with_embeddings', (
      SELECT COUNT(*)
      FROM product_embeddings pe
      WHERE pe.status = 'completed'
    ),
    'pending_embeddings', (
      SELECT COUNT(*)
      FROM product_embeddings pe
      WHERE pe.status = 'pending'
    ),
    'failed_embeddings', (
      SELECT COUNT(*)
      FROM product_embeddings pe
      WHERE pe.status = 'failed'
    ),
    'products_without_embeddings', (
      SELECT COUNT(*)
      FROM products p
      LEFT JOIN product_embeddings pe ON p.id = pe.product_id
      WHERE pe.product_id IS NULL
    ),
    'completion_percentage', (
      CASE
        WHEN (SELECT COUNT(*) FROM products) = 0 THEN 100
        ELSE ROUND(
          (SELECT COUNT(*) FROM product_embeddings WHERE status = 'completed') * 100.0 /
          (SELECT COUNT(*) FROM products), 2
        )
      END
    ),
    'last_generation_run', (
      SELECT json_build_object(
        'id', id,
        'started_at', started_at,
        'completed_at', completed_at,
        'status', status,
        'successful_embeddings', successful_embeddings,
        'failed_embeddings', failed_embeddings
      )
      FROM embedding_generation_runs
      ORDER BY started_at DESC
      LIMIT 1
    )
  );
$$;

-- Function to get products that need embeddings generated
CREATE OR REPLACE FUNCTION get_products_needing_embeddings(
  max_attempts INTEGER DEFAULT 3,
  batch_size INTEGER DEFAULT 100
)
RETURNS TABLE (
  product_id UUID,
  title TEXT,
  description TEXT,
  colors TEXT[],
  sizes TEXT[],
  regular_price DECIMAL,
  category_name TEXT
)
LANGUAGE SQL STABLE
AS $$
  -- Get products that don't have embeddings at all OR have failed embeddings with attempts < max_attempts
  SELECT
    p.id as product_id,
    p.title,
    p.description,
    p.colors,
    p.sizes,
    p.regular_price,
    c.name as category_name
  FROM products p
  LEFT JOIN categories c ON p.category_id = c.id
  LEFT JOIN product_embeddings pe ON p.id = pe.product_id
  WHERE
    pe.product_id IS NULL -- No embedding record
    OR (
      pe.status IN ('pending', 'failed')
      AND pe.generation_attempts < max_attempts
    )
  ORDER BY p.created_at DESC
  LIMIT batch_size;
$$;

-- Function to mark embedding generation as started
CREATE OR REPLACE FUNCTION start_embedding_generation_run(
  run_type_param VARCHAR DEFAULT 'full_generation',
  model_name_param VARCHAR DEFAULT 'all-MiniLM-L6-v2'
)
RETURNS UUID
LANGUAGE PLPGSQL
AS $$
DECLARE
  run_id UUID;
  product_count INTEGER;
BEGIN
  -- Count products that need embeddings
  SELECT COUNT(*) INTO product_count
  FROM get_products_needing_embeddings();

  -- Insert new generation run
  INSERT INTO embedding_generation_runs (
    status,
    total_products,
    model_name,
    run_type,
    notes
  ) VALUES (
    'running',
    product_count,
    model_name_param,
    run_type_param,
    'Embedding generation started'
  ) RETURNING id INTO run_id;

  RETURN run_id;
END;
$$;

-- Function to complete embedding generation run
CREATE OR REPLACE FUNCTION complete_embedding_generation_run(
  run_id_param UUID,
  successful_count INTEGER DEFAULT 0,
  failed_count INTEGER DEFAULT 0,
  skipped_count INTEGER DEFAULT 0,
  error_details_param TEXT DEFAULT NULL
)
RETURNS BOOLEAN
LANGUAGE PLPGSQL
AS $$
BEGIN
  UPDATE embedding_generation_runs
  SET
    completed_at = now(),
    status = CASE
      WHEN failed_count = 0 THEN 'completed'
      WHEN successful_count = 0 THEN 'failed'
      ELSE 'partial'
    END,
    successful_embeddings = successful_count,
    failed_embeddings = failed_count,
    skipped_embeddings = skipped_count,
    processed_products = successful_count + failed_count + skipped_count,
    error_details = error_details_param,
    notes = CASE
      WHEN failed_count = 0 THEN 'All embeddings generated successfully'
      WHEN successful_count = 0 THEN 'Embedding generation failed completely'
      ELSE 'Embedding generation completed with some failures'
    END
  WHERE id = run_id_param;

  RETURN FOUND;
END;
$$;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON public.embedding_generation_runs TO authenticated;
GRANT EXECUTE ON FUNCTION check_embeddings_completion TO authenticated;
GRANT EXECUTE ON FUNCTION get_products_needing_embeddings TO authenticated;
GRANT EXECUTE ON FUNCTION start_embedding_generation_run TO authenticated;
GRANT EXECUTE ON FUNCTION complete_embedding_generation_run TO authenticated;

-- Update existing product_embeddings records to have 'completed' status if they have embeddings
UPDATE public.product_embeddings
SET status = 'completed', generation_attempts = 1
WHERE embedding IS NOT NULL AND status = 'pending';

COMMENT ON TABLE public.embedding_generation_runs IS 'Tracks embedding generation runs to prevent duplicates and monitor progress';
COMMENT ON FUNCTION check_embeddings_completion IS 'Returns comprehensive status of embedding generation completion';
COMMENT ON FUNCTION get_products_needing_embeddings IS 'Gets products that need embeddings generated, with retry limit';