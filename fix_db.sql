-- 修复数据库表结构 - 添加缺失的列
-- 执行方式: docker exec -i ai-eval-postgres psql -U eval -d ai_eval

-- 检查并添加 score 列到 eval_results 表
ALTER TABLE eval_results ADD COLUMN IF NOT EXISTS score FLOAT;
