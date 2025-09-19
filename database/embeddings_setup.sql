-- Product Embeddings Table Setup
-- This script creates the product_embeddings table and necessary functions

-- Create the product_embeddings table
create table if not exists public.product_embeddings (
  id uuid not null default gen_random_uuid (),
  product_id character varying(255) not null,
  product_text text not null,
  embedding public.vector null,
  embedding_model character varying(100) null default 'all-MiniLM-L6-v2'::character varying,
  created_at timestamp with time zone null default now(),
  updated_at timestamp with time zone null default now(),
  constraint product_embeddings_pkey primary key (id),
  constraint product_embeddings_product_id_key unique (product_id),
  constraint product_embeddings_product_id_fkey foreign key (product_id) references products (id) on delete cascade
) tablespace pg_default;

-- Create indexes for better performance
create index if not exists product_embeddings_cosine_idx on public.product_embeddings using ivfflat (embedding vector_cosine_ops)
with (lists = '100') tablespace pg_default;

create index if not exists idx_product_embeddings_product_id on public.product_embeddings using btree (product_id) tablespace pg_default;

create index if not exists idx_product_embeddings_model on public.product_embeddings using btree (embedding_model) tablespace pg_default;

-- Create function to update updated_at timestamp
create or replace function update_product_embeddings_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

-- Create trigger for auto-updating timestamps
create trigger if not exists trigger_update_product_embeddings_updated_at
    before update on product_embeddings
    for each row
    execute function update_product_embeddings_updated_at();

-- Function for semantic search using cosine similarity
create or replace function search_products_by_embedding(
  query_embedding vector,
  match_threshold float default 0.3,
  match_count int default 10
)
returns table (
  product_id varchar,
  similarity float
)
language sql stable
as $$
  select
    pe.product_id,
    1 - (pe.embedding <=> query_embedding) as similarity
  from product_embeddings pe
  where 1 - (pe.embedding <=> query_embedding) > match_threshold
  order by pe.embedding <=> query_embedding
  limit match_count;
$$;

-- Grant necessary permissions
grant usage on schema public to public;
grant all on public.product_embeddings to public;
grant execute on function search_products_by_embedding to public;

-- Sample query to test the setup (uncomment to test)
-- select * from search_products_by_embedding(
--   '[0.1, 0.2, 0.3]'::vector,  -- Replace with actual embedding
--   0.3,
--   5
-- );