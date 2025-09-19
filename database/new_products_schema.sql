-- New Products table schema matching provided requirements
-- This creates the exact table structure as specified

-- Drop existing products table if it exists (use with caution in production)
-- DROP TABLE IF EXISTS public.products CASCADE;

-- Create the new products table with exact schema as provided
CREATE TABLE IF NOT EXISTS public.products (
  session_id integer null,
  product_id text null,
  url text null,
  title text null,
  price text null,
  regular_price text null,
  sale_price text null,
  discount_percentage text null,
  is_on_sale boolean null,
  sku text null,
  product_sections jsonb null,
  description text null,
  colors text[] null,
  sizes text[] null,
  available_sizes text[] null,
  out_of_stock_sizes text[] null,
  size_availability jsonb null,
  other_options text[] null,
  images text[] null,
  image_count integer null,
  created_at timestamp with time zone null default now(),
  category_id uuid not null,
  id uuid not null default gen_random_uuid (),

  -- Constraints
  CONSTRAINT products__id_key UNIQUE (id),
  CONSTRAINT products_product_id_key UNIQUE (product_id),
  CONSTRAINT products_category_id_fkey FOREIGN KEY (category_id) REFERENCES categories (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT products_session_id_fkey FOREIGN KEY (session_id) REFERENCES scrape_sessions (id)
) TABLESPACE pg_default;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_products_product_id ON public.products USING btree (product_id) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_products_session_id ON public.products USING btree (session_id) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_products_title ON public.products USING btree (title) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_products_price ON public.products USING btree (price) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_products_created_at ON public.products USING btree (created_at) TABLESPACE pg_default;

-- Additional performance indexes for arrays and jsonb
CREATE INDEX IF NOT EXISTS idx_products_colors ON public.products USING GIN (colors) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_products_sizes ON public.products USING GIN (sizes) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_products_available_sizes ON public.products USING GIN (available_sizes) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_products_product_sections ON public.products USING GIN (product_sections) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_products_size_availability ON public.products USING GIN (size_availability) TABLESPACE pg_default;

-- Create trigger for updating updated_at column (assuming the function exists)
CREATE TRIGGER IF NOT EXISTS update_products_updated_at
  BEFORE UPDATE ON products
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column ();

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON public.products TO authenticated;
GRANT USAGE ON SCHEMA public TO authenticated;

-- Create a function to search products by embedding (needed for semantic search)
-- This function should be compatible with the existing embedding search
CREATE OR REPLACE FUNCTION search_products_by_embedding(
  query_embedding vector,
  match_threshold float DEFAULT 0.5,
  match_count int DEFAULT 15
)
RETURNS TABLE (
  product_id uuid,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  -- This is a placeholder function
  -- You'll need to implement the actual vector similarity search
  -- based on your embeddings table structure

  RETURN QUERY
  SELECT
    pe.product_id::uuid,
    1 - (pe.embedding <=> query_embedding) as similarity
  FROM product_embeddings pe
  WHERE 1 - (pe.embedding <=> query_embedding) > match_threshold
  ORDER BY pe.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Sample insert statement for testing (comment out in production)
/*
INSERT INTO public.products (
  session_id, product_id, url, title, price, regular_price, sale_price,
  discount_percentage, is_on_sale, sku, product_sections, description,
  colors, sizes, available_sizes, out_of_stock_sizes, size_availability,
  other_options, images, image_count, category_id
) VALUES (
  1,
  '110200838x',
  'https://shopecs.com/collections/women-footwear/products/110200838x',
  'Bit Strap',
  '3400',
  '3400',
  null,
  null,
  false,
  '110200838X004036',
  '{"Style": "Smart Casual Slipper", "Design": "Broad vamp with metal detail", "Material": "Faux Leather"}',
  'This slipper offers a sleek, refined design featuring a wide vamp strap adorned with metallic bit hardware. The structured shape makes it suitable for both casual and slightly dressy occasions.',
  ARRAY['Black'],
  ARRAY['36','37','38','39','40','41','42'],
  ARRAY['36','37','38','39','40','41','42'],
  ARRAY[]::text[],
  '{"36": true, "37": true, "38": true, "39": true, "40": true, "41": true, "42": true}',
  ARRAY[]::text[],
  ARRAY[
    'https://shopecs.com/cdn/shop/files/DSC_1960_08e8d428-e676-4ba9-8462-bd6cd1479dbc.jpg?v=1756708892&width=1920',
    'https://shopecs.com/cdn/shop/files/DSC_2024_d2d32151-5f89-4055-8488-7cd14f7db2ca.jpg?v=1756708892&width=1920'
  ],
  5,
  'ae8a00c7-736e-4d83-9b30-ca86599f8682'::uuid
);
*/