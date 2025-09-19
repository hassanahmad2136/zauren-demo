-- Cart Database Schema
-- SQL script to create cart and order related tables

-- Create user_sessions table for tracking user sessions
CREATE TABLE IF NOT EXISTS public.user_sessions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  session_id text NOT NULL,
  user_id text NOT NULL,
  user_name text NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  expires_at timestamp with time zone NOT NULL DEFAULT (now() + interval '30 days'),
  is_active boolean NOT NULL DEFAULT true,

  -- Constraints
  CONSTRAINT user_sessions_pkey PRIMARY KEY (id),
  CONSTRAINT user_sessions_session_id_key UNIQUE (session_id),
  CONSTRAINT user_sessions_user_id_session_active UNIQUE (user_id, is_active) DEFERRABLE INITIALLY DEFERRED
);

-- Create shopping_carts table
CREATE TABLE IF NOT EXISTS public.shopping_carts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT shopping_carts_pkey PRIMARY KEY (id),
  CONSTRAINT shopping_carts_session_id_fkey FOREIGN KEY (session_id) REFERENCES user_sessions (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT shopping_carts_session_unique UNIQUE (session_id)
);

-- Create cart_items table
CREATE TABLE IF NOT EXISTS public.cart_items (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  cart_id uuid NOT NULL,
  product_id uuid NOT NULL,
  quantity integer NOT NULL DEFAULT 1,
  size text NULL,
  color text NULL,
  unit_price decimal(10,2) NOT NULL,
  total_price decimal(10,2) NOT NULL,
  added_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT cart_items_pkey PRIMARY KEY (id),
  CONSTRAINT cart_items_cart_id_fkey FOREIGN KEY (cart_id) REFERENCES shopping_carts (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT cart_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES products (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT cart_items_quantity_check CHECK (quantity > 0),
  CONSTRAINT cart_items_unit_price_check CHECK (unit_price >= 0),
  CONSTRAINT cart_items_total_price_check CHECK (total_price >= 0),
  CONSTRAINT cart_items_cart_product_size_color_unique UNIQUE (cart_id, product_id, size, color)
);

-- Create orders table for checkout
CREATE TABLE IF NOT EXISTS public.orders (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  order_number text NOT NULL,
  session_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'pending',
  total_amount decimal(10,2) NOT NULL,
  currency text NOT NULL DEFAULT 'PKR',
  customer_name text NULL,
  customer_phone text NULL,
  customer_email text NULL,
  shipping_address jsonb NULL,
  billing_address jsonb NULL,
  payment_method text NULL,
  payment_status text NOT NULL DEFAULT 'pending',
  notes text NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  shipped_at timestamp with time zone NULL,
  delivered_at timestamp with time zone NULL,

  -- Constraints
  CONSTRAINT orders_pkey PRIMARY KEY (id),
  CONSTRAINT orders_order_number_key UNIQUE (order_number),
  CONSTRAINT orders_session_id_fkey FOREIGN KEY (session_id) REFERENCES user_sessions (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT orders_status_check CHECK (status IN ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled')),
  CONSTRAINT orders_payment_status_check CHECK (payment_status IN ('pending', 'paid', 'failed', 'refunded')),
  CONSTRAINT orders_total_amount_check CHECK (total_amount >= 0)
);

-- Create order_items table
CREATE TABLE IF NOT EXISTS public.order_items (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  order_id uuid NOT NULL,
  product_id uuid NOT NULL,
  quantity integer NOT NULL,
  size text NULL,
  color text NULL,
  unit_price decimal(10,2) NOT NULL,
  total_price decimal(10,2) NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT order_items_pkey PRIMARY KEY (id),
  CONSTRAINT order_items_order_id_fkey FOREIGN KEY (order_id) REFERENCES orders (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT order_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES products (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT order_items_quantity_check CHECK (quantity > 0),
  CONSTRAINT order_items_unit_price_check CHECK (unit_price >= 0),
  CONSTRAINT order_items_total_price_check CHECK (total_price >= 0)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON public.user_sessions USING btree (user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_session_id ON public.user_sessions USING btree (session_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_is_active ON public.user_sessions USING btree (is_active);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON public.user_sessions USING btree (expires_at);

CREATE INDEX IF NOT EXISTS idx_shopping_carts_session_id ON public.shopping_carts USING btree (session_id);
CREATE INDEX IF NOT EXISTS idx_shopping_carts_updated_at ON public.shopping_carts USING btree (updated_at);

CREATE INDEX IF NOT EXISTS idx_cart_items_cart_id ON public.cart_items USING btree (cart_id);
CREATE INDEX IF NOT EXISTS idx_cart_items_product_id ON public.cart_items USING btree (product_id);
CREATE INDEX IF NOT EXISTS idx_cart_items_added_at ON public.cart_items USING btree (added_at);

CREATE INDEX IF NOT EXISTS idx_orders_session_id ON public.orders USING btree (session_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_number ON public.orders USING btree (order_number);
CREATE INDEX IF NOT EXISTS idx_orders_status ON public.orders USING btree (status);
CREATE INDEX IF NOT EXISTS idx_orders_payment_status ON public.orders USING btree (payment_status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON public.orders USING btree (created_at);

CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON public.order_items USING btree (order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON public.order_items USING btree (product_id);

-- Create triggers for updating updated_at columns
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers
CREATE TRIGGER IF NOT EXISTS update_user_sessions_updated_at
  BEFORE UPDATE ON user_sessions
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER IF NOT EXISTS update_shopping_carts_updated_at
  BEFORE UPDATE ON shopping_carts
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER IF NOT EXISTS update_cart_items_updated_at
  BEFORE UPDATE ON cart_items
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER IF NOT EXISTS update_orders_updated_at
  BEFORE UPDATE ON orders
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_sessions TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.shopping_carts TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.cart_items TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.orders TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.order_items TO authenticated;

-- Create helper functions for cart management

-- Function to get or create user session
CREATE OR REPLACE FUNCTION get_or_create_user_session(
  p_user_id text,
  p_user_name text DEFAULT NULL
)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
  session_uuid uuid;
BEGIN
  -- First, deactivate any existing active sessions for this user
  UPDATE user_sessions 
  SET is_active = false 
  WHERE user_id = p_user_id AND is_active = true;

  -- Create new session
  INSERT INTO user_sessions (session_id, user_id, user_name)
  VALUES ('cli_session_' || p_user_id, p_user_id, COALESCE(p_user_name, 'CLI User'))
  RETURNING id INTO session_uuid;

  RETURN session_uuid;
END;
$$;

-- Function to get or create shopping cart for session
CREATE OR REPLACE FUNCTION get_or_create_shopping_cart(
  p_session_id uuid
)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
  cart_uuid uuid;
BEGIN
  -- Try to get existing cart
  SELECT id INTO cart_uuid
  FROM shopping_carts
  WHERE session_id = p_session_id;

  -- If no cart exists, create one
  IF cart_uuid IS NULL THEN
    INSERT INTO shopping_carts (session_id)
    VALUES (p_session_id)
    RETURNING id INTO cart_uuid;
  END IF;

  RETURN cart_uuid;
END;
$$;

-- Function to add item to cart
CREATE OR REPLACE FUNCTION add_to_cart(
  p_session_id uuid,
  p_product_id uuid,
  p_quantity integer DEFAULT 1,
  p_size text DEFAULT NULL,
  p_color text DEFAULT NULL,
  p_unit_price decimal DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
  cart_id uuid;
  existing_quantity integer := 0;
  product_price decimal;
  result jsonb;
BEGIN
  -- Get or create cart
  cart_id := get_or_create_shopping_cart(p_session_id);

  -- Get product price if not provided
  IF p_unit_price IS NULL THEN
    SELECT COALESCE(CAST(sale_price AS decimal), CAST(price AS decimal), 0)
    INTO product_price
    FROM products
    WHERE id = p_product_id;
  ELSE
    product_price := p_unit_price;
  END IF;

  -- Check if item already exists in cart
  SELECT quantity INTO existing_quantity
  FROM cart_items
  WHERE cart_id = cart_id 
    AND product_id = p_product_id 
    AND COALESCE(size, '') = COALESCE(p_size, '')
    AND COALESCE(color, '') = COALESCE(p_color, '');

  IF existing_quantity > 0 THEN
    -- Update existing item
    UPDATE cart_items
    SET quantity = existing_quantity + p_quantity,
        total_price = (existing_quantity + p_quantity) * product_price,
        updated_at = NOW()
    WHERE cart_id = cart_id 
      AND product_id = p_product_id 
      AND COALESCE(size, '') = COALESCE(p_size, '')
      AND COALESCE(color, '') = COALESCE(p_color, '');
      
    result := jsonb_build_object(
      'status', 'updated',
      'quantity', existing_quantity + p_quantity
    );
  ELSE
    -- Insert new item
    INSERT INTO cart_items (cart_id, product_id, quantity, size, color, unit_price, total_price)
    VALUES (cart_id, p_product_id, p_quantity, p_size, p_color, product_price, p_quantity * product_price);
    
    result := jsonb_build_object(
      'status', 'added',
      'quantity', p_quantity
    );
  END IF;

  RETURN result;
END;
$$;

-- Function to get cart contents
CREATE OR REPLACE FUNCTION get_cart_contents(
  p_session_id uuid
)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
  result jsonb;
BEGIN
  SELECT jsonb_build_object(
    'items', COALESCE(jsonb_agg(
      jsonb_build_object(
        'id', ci.id,
        'product_id', ci.product_id,
        'title', p.title,
        'quantity', ci.quantity,
        'size', ci.size,
        'color', ci.color,
        'unit_price', ci.unit_price,
        'total_price', ci.total_price,
        'product_details', jsonb_build_object(
          'title', p.title,
          'description', p.description,
          'images', p.images,
          'colors', p.colors,
          'sizes', p.sizes
        )
      )
    ), '[]'::jsonb),
    'total', COALESCE(SUM(ci.total_price), 0)
  ) INTO result
  FROM shopping_carts sc
  LEFT JOIN cart_items ci ON sc.id = ci.cart_id
  LEFT JOIN products p ON ci.product_id = p.id
  WHERE sc.session_id = p_session_id
  GROUP BY sc.id;

  RETURN COALESCE(result, '{"items": [], "total": 0}'::jsonb);
END;
$$;

-- Function to remove item from cart
CREATE OR REPLACE FUNCTION remove_from_cart(
  p_session_id uuid,
  p_product_id uuid,
  p_size text DEFAULT NULL,
  p_color text DEFAULT NULL
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
  cart_id uuid;
  deleted_count integer;
BEGIN
  -- Get cart
  SELECT id INTO cart_id
  FROM shopping_carts
  WHERE session_id = p_session_id;

  IF cart_id IS NULL THEN
    RETURN false;
  END IF;

  -- Delete item
  DELETE FROM cart_items
  WHERE cart_id = cart_id 
    AND product_id = p_product_id 
    AND COALESCE(size, '') = COALESCE(p_size, '')
    AND COALESCE(color, '') = COALESCE(p_color, '');

  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  
  RETURN deleted_count > 0;
END;
$$;

-- Function to clear cart
CREATE OR REPLACE FUNCTION clear_cart(
  p_session_id uuid
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
  cart_id uuid;
BEGIN
  -- Get cart
  SELECT id INTO cart_id
  FROM shopping_carts
  WHERE session_id = p_session_id;

  IF cart_id IS NULL THEN
    RETURN false;
  END IF;

  -- Delete all items
  DELETE FROM cart_items WHERE cart_id = cart_id;
  
  RETURN true;
END;
$$;