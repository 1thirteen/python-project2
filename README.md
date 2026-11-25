# python-project2

《挑战课题—Python 编程》课题 II：**数据库编程 —— 基于 Python 的管理信息系统设计**。

本仓库当前存放课题2《学生管理系统》的**数据库设计文档**，尚未提交可运行的系统代码。

## 文档

| 文件 | 内容 |
| ---- | ---- |
| [docs/课题2-数据库内容说明.md](docs/课题2-数据库内容说明.md) | 数据库里有什么、为什么这么设计、怎么被用起来：4 张表的字段与约束、ER 图、3 个视图、触发器、索引、41 条真实数据的快照、增删改查的实际执行记录、Python 访问层参考实现、12 个设计取舍问答 |

文档附录 A、B 分别是完整的 `schema.sql` 与 `seed.sql`，复制出来即可建库：

```bash
sqlite3 student.db < schema.sql
sqlite3 student.db < seed.sql
```

## 数据模型一览

```
classes 1 ──< students 1 ──< scores >── 1 courses
   (班级)        (学生)         (成绩)        (课程)
```

- `classes`：班级、专业、年级、班主任
- `students`：学号、姓名、性别、联系方式，`class_id` 外键（可为空 = 未分班）
- `courses`：课程号、课程名、学分、学时
- `scores`：复合主键 `(student_id, course_id, term)`，成绩可空（未录入），改分自动刷新 `updated_at`

## 环境

文档中的全部 SQL 与查询结果均在 SQLite 3.53.1 + Python 3.12 上实际执行，零第三方依赖。
