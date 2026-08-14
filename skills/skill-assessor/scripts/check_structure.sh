#!/bin/bash
# Skill 结构检查脚本
# 用法: bash check_structure.sh <skill-path>
# 示例: bash check_structure.sh .codebuddy/skills/my-skill

set -e

SKILL_PATH="${1:-.}"

echo "========================================="
echo "  Skill 结构检查: $SKILL_PATH"
echo "========================================="
echo ""

ERRORS=0
WARNINGS=0

# 1. 检查 SKILL.md 是否存在（大小写敏感）
echo "--- 检查 SKILL.md ---"
if [ -f "$SKILL_PATH/SKILL.md" ]; then
    echo "✅ SKILL.md 存在"
else
    echo "❌ SKILL.md 不存在或命名错误"
    # 检查常见错误命名
    for f in skill.md Skill.md SKILL.MD readme.md README.md; do
        if [ -f "$SKILL_PATH/$f" ]; then
            echo "   → 发现错误命名: $f"
        fi
    done
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 2. 检查文件夹命名
echo "--- 检查文件夹命名 ---"
FOLDER_NAME=$(basename "$SKILL_PATH")
if echo "$FOLDER_NAME" | grep -qE '^[a-z0-9]+(-[a-z0-9]+)*$'; then
    echo "✅ 文件夹名合规: $FOLDER_NAME"
else
    echo "❌ 文件夹名不合规: $FOLDER_NAME (应为 kebab-case)"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 3. 检查 YAML frontmatter
echo "--- 检查 YAML Frontmatter ---"
if [ -f "$SKILL_PATH/SKILL.md" ]; then
    FIRST_LINE=$(head -1 "$SKILL_PATH/SKILL.md")
    if [ "$FIRST_LINE" = "---" ]; then
        echo "✅ Frontmatter 起始标记正确"
        
        # 检查 name 字段
        NAME_LINE=$(grep -m1 "^name:" "$SKILL_PATH/SKILL.md" 2>/dev/null || echo "")
        if [ -n "$NAME_LINE" ]; then
            NAME_VALUE=$(echo "$NAME_LINE" | sed 's/name: *//;s/"//g;s/'"'"'//g')
            echo "✅ name 字段存在: $NAME_VALUE"
            
            # 检查 name 是否与文件夹名一致
            if [ "$NAME_VALUE" = "$FOLDER_NAME" ]; then
                echo "✅ name 与文件夹名一致"
            else
                echo "⚠️ name ($NAME_VALUE) 与文件夹名 ($FOLDER_NAME) 不一致"
                WARNINGS=$((WARNINGS + 1))
            fi
        else
            echo "❌ 缺少 name 字段"
            ERRORS=$((ERRORS + 1))
        fi
        
        # 检查 description 字段
        DESC_LINE=$(grep -m1 "^description:" "$SKILL_PATH/SKILL.md" 2>/dev/null || echo "")
        if [ -n "$DESC_LINE" ]; then
            echo "✅ description 字段存在"
        else
            echo "❌ 缺少 description 字段"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo "❌ 文件未以 '---' 开头，frontmatter 格式错误"
        ERRORS=$((ERRORS + 1))
    fi
fi
echo ""

# 4. 检查根目录违规文件
echo "--- 检查根目录文件 ---"
ROOT_FILES=$(find "$SKILL_PATH" -maxdepth 1 -type f ! -name "SKILL.md" 2>/dev/null)
if [ -z "$ROOT_FILES" ]; then
    echo "✅ 根目录无违规文件"
else
    echo "⚠️ 根目录存在非 SKILL.md 文件:"
    echo "$ROOT_FILES" | while read -r f; do
        echo "   → $(basename "$f")"
    done
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# 5. 检查子目录
echo "--- 检查子目录结构 ---"
for dir in scripts references assets; do
    if [ -d "$SKILL_PATH/$dir" ]; then
        FILE_COUNT=$(find "$SKILL_PATH/$dir" -type f | wc -l | tr -d ' ')
        if [ "$FILE_COUNT" -gt 0 ]; then
            echo "✅ $dir/ 存在 ($FILE_COUNT 个文件)"
        else
            echo "⚠️ $dir/ 存在但为空"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
done
echo ""

# 6. 检查正文长度
echo "--- 检查正文长度 ---"
if [ -f "$SKILL_PATH/SKILL.md" ]; then
    LINE_COUNT=$(wc -l < "$SKILL_PATH/SKILL.md" | tr -d ' ')
    WORD_COUNT=$(wc -w < "$SKILL_PATH/SKILL.md" | tr -d ' ')
    echo "   行数: $LINE_COUNT (建议 ≤500)"
    echo "   词数: $WORD_COUNT (建议 ≤5000)"
    
    if [ "$LINE_COUNT" -le 500 ]; then
        echo "✅ 行数合规"
    else
        echo "⚠️ 行数超出建议值"
        WARNINGS=$((WARNINGS + 1))
    fi
fi
echo ""

# 7. 汇总
echo "========================================="
echo "  检查结果汇总"
echo "========================================="
echo "  ❌ 错误: $ERRORS"
echo "  ⚠️ 警告: $WARNINGS"
echo ""

if [ "$ERRORS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    echo "  🎉 结构检查全部通过！"
elif [ "$ERRORS" -eq 0 ]; then
    echo "  ✅ 无严重错误，有 $WARNINGS 个警告可优化"
else
    echo "  🔴 存在 $ERRORS 个错误需要修复"
fi

exit $ERRORS
