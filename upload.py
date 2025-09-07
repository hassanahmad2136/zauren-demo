import os
from groq import Groq
from supabase import create_client, Client

# Set environment variables or hardcode them here
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize clientGenerates
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

def generate_new_description(product):
    prompt = f"""
Explain the following product clearly in 3–4 lines, suitable for a product detail page. Do not use marketing language.

Include:
- What the product is
- What it’s used for
- Any key features (like size, material, compatibility, etc.)
- Address common questions customers might have

Product Name: {product['name']}
Current Description: {product.get('description') or 'None'}
Price: ${product['unit_price']}
Quantity in Stock: {product['quantity']}
SKU: {product.get('sku') or 'N/A'}
"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()

def update_descriptions():
    # Fetch products from Supabase
    products = supabase.table("products").select("*").execute().data

    for product in products:
        try:
            new_desc = generate_new_description(product)
            # print(f"\nUpdated description for {product['name']}:\n{new_desc}\n")
            # Update the product in Supabase
            supabase.table("products").update({
                "description": new_desc
            }).eq("id", product["id"]).execute()
        except Exception as e:
            # print(f"Error processing product {product['name']}: {e}")
            pass

if __name__ == "__main__":
    update_descriptions()
