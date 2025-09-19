-- Fix interactive_messages table by adding missing columns
-- This script adds product_id and category_id columns to the interactive_messages table

-- Add product_id column as UUID with foreign key to products table
ALTER TABLE public.interactive_messages 
ADD COLUMN IF NOT EXISTS product_id UUID;

-- Add category_id column as UUID with foreign key to categories table  
ALTER TABLE public.interactive_messages 
ADD COLUMN IF NOT EXISTS category_id UUID;

-- Add foreign key constraints
-- Note: Using CASCADE delete to maintain referential integrity
ALTER TABLE public.interactive_messages 
ADD CONSTRAINT IF NOT EXISTS fk_interactive_messages_product_id 
FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE;

ALTER TABLE public.interactive_messages 
ADD CONSTRAINT IF NOT EXISTS fk_interactive_messages_category_id 
FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE;

-- Add indexes for better performance on the new foreign key columns
CREATE INDEX IF NOT EXISTS idx_interactive_messages_product_id 
ON public.interactive_messages USING btree (product_id) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_interactive_messages_category_id 
ON public.interactive_messages USING btree (category_id) TABLESPACE pg_default;

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON public.interactive_messages TO authenticated;

-- Show the updated table structure
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'interactive_messages' 
AND table_schema = 'public'
ORDER BY ordinal_position;
