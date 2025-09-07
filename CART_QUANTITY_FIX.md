# Cart Quantity Management Test

This test verifies the cart quantity bug fix where removing items now properly handles quantities instead of removing entire items.

## Test Scenario:
1. Add 2 White Cotton Kurtas to cart (quantity = 2)
2. Request to remove 1 White Cotton Kurta
3. Verify that 1 White Cotton Kurta remains in cart (quantity = 1)

## Expected Behavior:
- **Before Fix**: Removing "1 White Cotton Kurta" would remove the entire item (quantity 2)
- **After Fix**: Removing "1 White Cotton Kurta" reduces quantity from 2 to 1

## Code Changes Made:

### In `update_cart_remove_products()` function:

**Before (Buggy):**
```python
# Remove the product - REMOVED ALL ITEMS WITH SAME NAME
user_session['cart']['items'] = [
    item for item in user_session['cart']['items']
    if isinstance(item, dict) and item.get('name', '').lower() != product_name.lower()
]
```

**After (Fixed):**
```python
# Find the product in cart and handle quantity removal
for item in user_session['cart']['items']:
    if item.get('name', '').lower() == product_name.lower():
        current_quantity = int(item.get('quantity', 0))
        
        if current_quantity <= quantity_to_remove:
            # Remove item completely if requested quantity >= current quantity
            # (don't add to items_to_keep)
        else:
            # Reduce quantity
            item['quantity'] = current_quantity - quantity_to_remove
            items_to_keep.append(item)
```

## Key Improvements:
1. **Quantity-Aware Removal**: Now checks the quantity to remove vs current quantity
2. **Partial Removal**: If removing less than total quantity, reduces the quantity
3. **Complete Removal**: If removing equal or more than total quantity, removes the item entirely
4. **Better Logging**: More detailed logs about quantity changes

## Test Commands:
To manually test this fix:
1. Add items with quantity > 1 to cart
2. Request removal of quantity < total quantity  
3. Verify the remaining quantity is correct

This fix ensures the cart behaves like a real shopping cart where you can remove specific quantities of items.
