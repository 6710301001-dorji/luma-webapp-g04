-- popular_tags.sql
-- ดึง Tag ยอดนิยมเรียงตามจำนวนภาพที่ถูกนำไปใช้ สำหรับทำ Tag Cloud หรือสถิติ
-- เทคนิค: JOIN + GROUP BY + COUNT + ORDER BY DESC + LIMIT
-- อ้างอิง: Resource_SQL_Database/3_SQL for Data Analysis.pdf · Issue #24

SELECT
    t.id,
    t.name,
    COUNT(at.asset_id) AS asset_count
FROM tags t
LEFT JOIN asset_tags at ON t.id = at.tag_id
GROUP BY t.id, t.name
ORDER BY asset_count DESC, t.name ASC
LIMIT :limit_count;
