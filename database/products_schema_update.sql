-- Products table schema update for ECS Shoe Store
-- This script updates the products table to handle the new schema requirements

-- First, let's add the new columns for the enhanced shoe store schema
ALTER TABLE products
ADD COLUMN IF NOT EXISTS colors TEXT[],
ADD COLUMN IF NOT EXISTS sizes TEXT[],
ADD COLUMN IF NOT EXISTS available_sizes TEXT[],
ADD COLUMN IF NOT EXISTS images TEXT[],
ADD COLUMN IF NOT EXISTS regular_price DECIMAL(10,2),
ADD COLUMN IF NOT EXISTS sale_price DECIMAL(10,2),
ADD COLUMN IF NOT EXISTS brand VARCHAR(100);

-- Update existing data to work with new schema
-- Convert single color to colors array (if color column exists)
UPDATE products
SET colors = ARRAY[color]
WHERE color IS NOT NULL
AND (colors IS NULL OR array_length(colors, 1) IS NULL);

-- Set regular_price from existing unit_price or fixed_price
UPDATE products
SET regular_price = COALESCE(unit_price, fixed_price, 0)
WHERE regular_price IS NULL;

-- Create indexes for better performance on new columns
CREATE INDEX IF NOT EXISTS idx_products_colors ON products USING GIN (colors);
CREATE INDEX IF NOT EXISTS idx_products_sizes ON products USING GIN (sizes);
CREATE INDEX IF NOT EXISTS idx_products_available_sizes ON products USING GIN (available_sizes);
CREATE INDEX IF NOT EXISTS idx_products_regular_price ON products (regular_price);
CREATE INDEX IF NOT EXISTS idx_products_sale_price ON products (sale_price) WHERE sale_price IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_products_brand ON products (brand);

-- Create a function to get effective price (sale_price if available, otherwise regular_price)
CREATE OR REPLACE FUNCTION get_effective_price(p_regular_price DECIMAL, p_sale_price DECIMAL)
RETURNS DECIMAL AS $$
BEGIN
    RETURN COALESCE(NULLIF(p_sale_price, 0), p_regular_price);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create a view for products with computed effective prices
CREATE OR REPLACE VIEW products_with_pricing AS
SELECT
    *,
    get_effective_price(regular_price, sale_price) as effective_price,
    CASE
        WHEN sale_price IS NOT NULL AND sale_price > 0 AND sale_price < regular_price
        THEN ROUND(((regular_price - sale_price) / regular_price * 100), 1)
        ELSE NULL
    END as discount_percentage,
    CASE
        WHEN sale_price IS NOT NULL AND sale_price > 0 AND sale_price < regular_price
        THEN true
        ELSE false
    END as is_on_sale
FROM products;

-- Grant permissions
GRANT SELECT ON products_with_pricing TO PUBLIC;
GRANT EXECUTE ON FUNCTION get_effective_price TO PUBLIC;

-- Sample data structure for reference (comment out in production)
/*
Example product with new schema:
{
    "id": "uuid",
    "name": "Comfortable Leather Chappal",
    "description": "Handcrafted leather chappal for daily wear",
    "regular_price": 2500.00,
    "sale_price": 2000.00,  -- null if not on sale
    "colors": ["brown", "black"],
    "sizes": ["7", "8", "9", "10"],
    "available_sizes": ["7", "8", "9"],  -- sizes currently in stock
    "images": ["image1.jpg", "image2.jpg"],
    "material": "leather",
    "style": "casual",
    "brand": "ECS Classic",
    "category_id": "category-uuid",
    "quantity": 25
}
*/