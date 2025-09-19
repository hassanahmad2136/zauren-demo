-- Migration script to update existing products table to new schema
-- This script safely migrates data while preserving existing information

-- First, let's create a backup of the current products table
CREATE TABLE IF NOT EXISTS products_backup AS SELECT * FROM products;

-- Add new columns to existing products table if they don't exist
ALTER TABLE products
ADD COLUMN IF NOT EXISTS session_id integer,
ADD COLUMN IF NOT EXISTS product_id text,
ADD COLUMN IF NOT EXISTS url text,
ADD COLUMN IF NOT EXISTS title text,
ADD COLUMN IF NOT EXISTS price text,
ADD COLUMN IF NOT EXISTS regular_price text,
ADD COLUMN IF NOT EXISTS sale_price text,
ADD COLUMN IF NOT EXISTS discount_percentage text,
ADD COLUMN IF NOT EXISTS is_on_sale boolean,
ADD COLUMN IF NOT EXISTS sku text,
ADD COLUMN IF NOT EXISTS product_sections jsonb,
ADD COLUMN IF NOT EXISTS colors text[],
ADD COLUMN IF NOT EXISTS sizes text[],
ADD COLUMN IF NOT EXISTS available_sizes text[],
ADD COLUMN IF NOT EXISTS out_of_stock_sizes text[],
ADD COLUMN IF NOT EXISTS size_availability jsonb,
ADD COLUMN IF NOT EXISTS other_options text[],
ADD COLUMN IF NOT EXISTS images text[],
ADD COLUMN IF NOT EXISTS image_count integer;

-- Migrate existing data to new columns
-- Update title from existing name column if it exists
UPDATE products
SET title = name
WHERE title IS NULL AND name IS NOT NULL;

-- Update product_id from existing id if it's text format
UPDATE products
SET product_id = id::text
WHERE product_id IS NULL AND id IS NOT NULL;

-- Update regular_price from existing price columns
UPDATE products
SET regular_price = COALESCE(unit_price::text, fixed_price::text, price)
WHERE regular_price IS NULL;

-- Update price from regular_price if price is null
UPDATE products
SET price = regular_price
WHERE price IS NULL AND regular_price IS NOT NULL;

-- Set is_on_sale based on sale_price
UPDATE products
SET is_on_sale = (sale_price IS NOT NULL AND sale_price != '' AND sale_price::numeric > 0 AND sale_price::numeric < regular_price::numeric)
WHERE is_on_sale IS NULL;

-- Calculate discount_percentage
UPDATE products
SET discount_percentage = CASE
    WHEN sale_price IS NOT NULL
         AND sale_price != ''
         AND regular_price IS NOT NULL
         AND regular_price != ''
         AND sale_price::numeric < regular_price::numeric
    THEN ROUND(((regular_price::numeric - sale_price::numeric) / regular_price::numeric * 100), 1)::text
    ELSE NULL
END
WHERE discount_percentage IS NULL;

-- Migrate colors from existing color column to array
UPDATE products
SET colors = ARRAY[color]
WHERE colors IS NULL AND color IS NOT NULL AND color != '';

-- Set image_count based on images array length
UPDATE products
SET image_count = array_length(images, 1)
WHERE image_count IS NULL AND images IS NOT NULL;

-- Create new constraints and indexes
ALTER TABLE products
ADD CONSTRAINT IF NOT EXISTS products_product_id_key UNIQUE (product_id);

-- Drop the constraint if it exists and recreate it
ALTER TABLE products DROP CONSTRAINT IF EXISTS products_session_id_fkey;
-- Only add the foreign key constraint if scrape_sessions table exists
-- ALTER TABLE products
-- ADD CONSTRAINT products_session_id_fkey FOREIGN KEY (session_id) REFERENCES scrape_sessions (id);

-- Create new indexes for performance
CREATE INDEX IF NOT EXISTS idx_products_product_id ON products USING btree (product_id);
CREATE INDEX IF NOT EXISTS idx_products_session_id ON products USING btree (session_id);
CREATE INDEX IF NOT EXISTS idx_products_title ON products USING btree (title);
CREATE INDEX IF NOT EXISTS idx_products_price ON products USING btree (price);
CREATE INDEX IF NOT EXISTS idx_products_colors ON products USING GIN (colors);
CREATE INDEX IF NOT EXISTS idx_products_sizes ON products USING GIN (sizes);
CREATE INDEX IF NOT EXISTS idx_products_available_sizes ON products USING GIN (available_sizes);
CREATE INDEX IF NOT EXISTS idx_products_product_sections ON products USING GIN (product_sections);
CREATE INDEX IF NOT EXISTS idx_products_size_availability ON products USING GIN (size_availability);

-- Update the trigger if the function exists
DROP TRIGGER IF EXISTS update_products_updated_at ON products;
-- CREATE TRIGGER update_products_updated_at
--   BEFORE UPDATE ON products
--   FOR EACH ROW
--   EXECUTE FUNCTION update_updated_at_column ();

-- Create a view to make the data compatible with the new schema expectations
CREATE OR REPLACE VIEW products_enhanced AS
SELECT
    id,
    session_id,
    COALESCE(product_id, id::text) as product_id,
    url,
    COALESCE(title, name) as title,
    COALESCE(price, regular_price) as price,
    regular_price,
    sale_price,
    discount_percentage,
    COALESCE(is_on_sale, false) as is_on_sale,
    sku,
    product_sections,
    COALESCE(description, '') as description,
    COALESCE(colors, ARRAY[]::text[]) as colors,
    COALESCE(sizes, ARRAY[]::text[]) as sizes,
    COALESCE(available_sizes, sizes, ARRAY[]::text[]) as available_sizes,
    COALESCE(out_of_stock_sizes, ARRAY[]::text[]) as out_of_stock_sizes,
    size_availability,
    COALESCE(other_options, ARRAY[]::text[]) as other_options,
    COALESCE(images, ARRAY[]::text[]) as images,
    COALESCE(image_count, 0) as image_count,
    created_at,
    category_id,
    -- Include any other existing columns that might be needed
    name,
    material,
    style,
    brand,
    quantity
FROM products;

-- Grant permissions on the new view
GRANT SELECT ON products_enhanced TO authenticated;

-- Verification queries (uncomment to run after migration)
/*
-- Check migration results
SELECT
    COUNT(*) as total_products,
    COUNT(title) as products_with_title,
    COUNT(product_id) as products_with_product_id,
    COUNT(colors) as products_with_colors,
    COUNT(images) as products_with_images,
    AVG(image_count) as avg_image_count
FROM products;

-- Sample of migrated data
SELECT
    id,
    product_id,
    title,
    price,
    regular_price,
    sale_price,
    is_on_sale,
    colors,
    sizes,
    image_count
FROM products
LIMIT 5;
*/