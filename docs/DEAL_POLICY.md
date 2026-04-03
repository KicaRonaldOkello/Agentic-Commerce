# Deal ranking policy (demo catalog)

This project ranks “best deals” **deterministically in SQL** for use by the storefront and future assistant tools.

## Primary rule (rows with a list price)

For products where `compare_at_price` is not null and **`compare_at_price > price`**:

- **Discount %** = `(compare_at_price - price) / compare_at_price`
- Higher discount % ranks higher.

## Ordering within the catalog

When `sort=deals` (or the **Best deals** view):

1. Products **with** a valid discount (as above) come **first**, ordered by discount % **descending**.
2. Products **without** a valid discount come **after**, ordered by:
   - `rating_average` **descending**
   - `price` **ascending**

## Optional filters

- **In stock only** (`in_stock_only=true`): `availability_status = 'in_stock'`.  
  The **Best deals** page uses this so we do not highlight out-of-stock SKUs.

## Category scope

Deals can be filtered by `product_type` (`phone` / `television`) like the rest of the catalog.

This policy is implemented in `search_products(..., sort="deals")` in `src/agentic_commerce/db.py`.
