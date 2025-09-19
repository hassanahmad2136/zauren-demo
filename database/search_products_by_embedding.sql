-- Create the RPC function for semantic search
CREATE OR REPLACE FUNCTION search_products_by_embedding(
  query_embedding vector(384),
  match_threshold float DEFAULT 0.3,
  match_count int DEFAULT 15
)
RETURNS TABLE (
  product_id varchar(255),
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    pe.product_id,
    (1 - (pe.embedding <=> query_embedding)) as similarity
  FROM product_embeddings pe
  WHERE (1 - (pe.embedding <=> query_embedding)) > match_threshold
  ORDER BY pe.embedding <=> query_embedding
  LIMIT match_count;
$$;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION search_products_by_embedding TO anon, authenticated;

-- Create index if it doesn't exist
CREATE INDEX IF NOT EXISTS product_embeddings_cosine_idx
ON product_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);