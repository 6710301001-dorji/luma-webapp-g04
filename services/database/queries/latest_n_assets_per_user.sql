-- latest_n_assets_per_user.sql
-- ดึงภาพล่าสุด N ภาพต่อผู้ใช้แต่ละคน สำหรับ Dashboard / Analytics
-- เทคนิค: Window Function ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)
-- อ้างอิง: Resource_SQL_Database/5_SQL Window Functions.pdf · Issue #24

WITH RankedAssets AS (
    SELECT
        id,
        user_id,
        prompt,
        file_path,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY user_id
            ORDER BY created_at DESC, id DESC
        ) AS rank_num
    FROM assets
)
SELECT
    id,
    user_id,
    prompt,
    file_path,
    created_at
FROM RankedAssets
WHERE rank_num <= :top_n
ORDER BY user_id, rank_num;
