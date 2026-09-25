-- filter_by_tags.sql
-- ค้นหา Asset ของผู้ใช้ที่ติด Tag ครบทุกตัวที่ระบุ (AND / Intersection)
-- เทคนิค: JOIN + GROUP BY + HAVING COUNT(DISTINCT tag_id) = num_tags
-- อ้างอิง: Resource_SQL_Database/2_SQL Joins.pdf · Issue #24

SELECT
    a.id,
    a.prompt,
    a.file_path,
    a.created_at
FROM assets a
JOIN asset_tags at ON a.id = at.asset_id
JOIN tags t ON at.tag_id = t.id
WHERE a.user_id = :user_id
  AND t.name IN :tag_names
GROUP BY a.id, a.prompt, a.file_path, a.created_at
HAVING COUNT(DISTINCT t.id) = :num_tags
ORDER BY a.created_at DESC, a.id DESC;
