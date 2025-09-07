import os
import cloudinary
import cloudinary.uploader
import requests

# --- Cloudinary Config ---
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# --- Supabase Config ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")

# --- Folder path ---
FOLDER_PATH = "product_images"

# --- Upload to Cloudinary ---
def upload_to_cloudinary(image_path, public_id):
    try:
        response = cloudinary.uploader.upload(
            image_path,
            public_id=public_id,
            folder="product_images"
        )
        return response['secure_url']
    except Exception as e:
        return None

# --- Update Supabase Record ---
def update_supabase_image_path(product_id, image_url):
    try:
        response = requests.patch(
            f"{SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
            json={"image_path": image_url},
            headers={
                "apikey": SUPABASE_API_KEY,
                "Authorization": f"Bearer {SUPABASE_API_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            timeout=10
        )
        if response.status_code in [200, 204]:
            pass
        else:
            pass
    except Exception as e:
        pass

# --- Process Images ---
def process_images(folder_path):
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            product_id = os.path.splitext(filename)[0]
            file_path = os.path.join(folder_path, filename)
            image_url = upload_to_cloudinary(file_path, public_id=product_id)
            if image_url:
                update_supabase_image_path(product_id, image_url)

# --- Run ---
if __name__ == "__main__":
    process_images(FOLDER_PATH)
