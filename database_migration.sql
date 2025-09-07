-- Migration for WhatsApp Bot Improvements
-- Run this SQL in your Supabase database

-- Create stock_reservations table for managing cart reservations
CREATE TABLE IF NOT EXISTS stock_reservations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for efficient queries
CREATE INDEX IF NOT EXISTS idx_stock_reservations_product_user 
ON stock_reservations(product_id, user_id);

CREATE INDEX IF NOT EXISTS idx_stock_reservations_updated_at 
ON stock_reservations(updated_at);

-- Create orders table for storing completed orders
CREATE TABLE IF NOT EXISTS orders (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled')),
    payment_method TEXT NOT NULL,
    payment_details TEXT,
    phone_number TEXT NOT NULL,
    delivery_address TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create order_items table for storing order line items
CREATE TABLE IF NOT EXISTS order_items (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);

-- Add RLS (Row Level Security) policies if needed
-- Note: Adjust these based on your authentication setup

-- Enable RLS on all tables
ALTER TABLE stock_reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;

-- Example policies (adjust based on your auth setup)
-- Allow service role to do everything
CREATE POLICY "Service role can manage stock_reservations" ON stock_reservations
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can manage orders" ON orders
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can manage order_items" ON order_items
    FOR ALL USING (auth.role() = 'service_role');

-- If you have user authentication, you might want policies like these:
-- CREATE POLICY "Users can view their own orders" ON orders
--     FOR SELECT USING (auth.uid()::text = user_id);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers to automatically update updated_at
CREATE TRIGGER update_stock_reservations_updated_at 
    BEFORE UPDATE ON stock_reservations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at 
    BEFORE UPDATE ON orders 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add quantity check constraint to products table if it doesn't exist
-- ALTER TABLE products ADD CONSTRAINT check_quantity_non_negative CHECK (quantity >= 0);

COMMENT ON TABLE stock_reservations IS 'Temporary stock reservations for items in user carts';
COMMENT ON TABLE orders IS 'Completed customer orders';
COMMENT ON TABLE order_items IS 'Individual items within orders';

-- Sample query to check available stock for a product
-- SELECT 
--     p.id,
--     p.name,
--     p.quantity as total_stock,
--     COALESCE(SUM(sr.quantity), 0) as reserved_stock,
--     p.quantity - COALESCE(SUM(sr.quantity), 0) as available_stock
-- FROM products p
-- LEFT JOIN stock_reservations sr ON p.id = sr.product_id
-- WHERE p.id = 'your-product-id'
-- GROUP BY p.id, p.name, p.quantity;
