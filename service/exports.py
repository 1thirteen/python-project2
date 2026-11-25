"""导出：学生成绩单（CSV / 可打印 HTML）、当前列表 CSV。"""

from __future__ import annotations

import csv
from pathlib import Path

from service import scores as score_service
from service import students as student_service


def _write_csv(path, headers, rows) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    return target


def write_students_csv(cfg, path) -> Path:
    rows = student_service.list_students(cfg)
    return _write_csv(
        path,
        ["学号", "姓名", "性别", "班级", "电话", "邮箱", "入学日期"],
        [[r["sno"], r["name"], r["gender"], r["class_name"], r["phone"] or "",
          r["email"] or "", r["enroll_date"]] for r in rows],
    )


def write_scores_csv(cfg, path, **filters) -> Path:
    rows = score_service.list_scores(cfg, **filters)
    return _write_csv(
        path,
        ["学号", "姓名", "班级", "课程", "学期", "成绩", "状态"],
        [[r["sno"], r["name"], r["class_name"], r["course"], r["term"],
          "" if r["score"] is None else f"{r['score']:g}", r["pass_state"]] for r in rows],
    )


def transcript_summary(cfg, student_id: int) -> dict:
    """成绩单的合计：已出分门数、学分、加权平均。"""
    rows = score_service.transcript(cfg, student_id)
    graded = [row for row in rows if row["score"] is not None]
    credits = sum(row["credit"] for row in graded)
    weighted = (round(sum(row["score"] * row["credit"] for row in graded) / credits, 2)
                if credits else None)
    return {"rows": rows, "graded": len(graded), "credits": credits, "weighted": weighted}


def write_transcript_csv(cfg, student_id: int, path) -> Path:
    student = student_service.get(cfg, student_id)
    summary = transcript_summary(cfg, student_id)
    headers = ["学号", "姓名", "课程", "学期", "学分", "成绩", "状态"]
    body = [[student["sno"], student["name"], row["course"], row["term"],
             f"{row['credit']:g}",
             "" if row["score"] is None else f"{row['score']:g}", row["pass_state"]]
            for row in summary["rows"]]
    return _write_csv(path, headers, body)


def transcript_html(cfg, student_id: int) -> str:
    """生成一页可打印的成绩单（浏览器打开后 Ctrl+P 即可）。"""
    student = student_service.get(cfg, student_id)
    summary = transcript_summary(cfg, student_id)
    weighted = "—" if summary["weighted"] is None else f"{summary['weighted']:.2f}"
    rows = "\n".join(
        f"""      <tr>
        <td>{row['course']}</td>
        <td class="center">{row['term']}</td>
        <td class="center">{row['credit']:g}</td>
        <td class="center">{'' if row['score'] is None else f"{row['score']:g}"}</td>
        <td class="center {row['pass_state']}">{row['pass_state']}</td>
      </tr>"""
        for row in summary["rows"]
    ) or """      <tr><td colspan="5" class="center muted">暂无成绩记录</td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>成绩单 · {student['sno']} {student['name']}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; margin: 0;
         padding: 32px; color: #1f2937; background: #f5f6f8; }}
  .sheet {{ max-width: 780px; margin: 0 auto; background: #fff; padding: 32px 36px;
            border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,.08); }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .sub {{ color: #6b7280; font-size: 13px; margin-bottom: 20px; }}
  .info {{ display: flex; gap: 28px; font-size: 14px; margin-bottom: 16px;
           padding-bottom: 12px; border-bottom: 1px solid #e5e7eb; }}
  .info b {{ color: #111827; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th, td {{ padding: 8px 10px; border-bottom: 1px solid #eef0f3; text-align: left; }}
  th {{ background: #f8fafc; color: #475569; font-weight: 600; }}
  .center {{ text-align: center; }}
  .pass {{ color: #047857; }}
  .fail {{ color: #b91c1c; }}
  .missing, .muted {{ color: #9ca3af; }}
  .total {{ margin-top: 14px; font-size: 14px; color: #374151; }}
  .actions {{ margin-top: 22px; text-align: right; }}
  button {{ padding: 8px 18px; border: 0; border-radius: 6px; background: #2563eb;
            color: #fff; font-size: 14px; cursor: pointer; }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .sheet {{ box-shadow: none; max-width: none; padding: 0; }}
    .actions {{ display: none; }}
  }}
</style>
</head>
<body>
  <div class="sheet">
    <h1>学生成绩单</h1>
    <div class="sub">课题2 · 学生管理系统</div>
    <div class="info">
      <span>学号 <b>{student['sno']}</b></span>
      <span>姓名 <b>{student['name']}</b></span>
      <span>班级 <b>{student['class_name']}</b></span>
    </div>
    <table>
      <thead>
        <tr><th>课程</th><th class="center">学期</th><th class="center">学分</th>
            <th class="center">成绩</th><th class="center">状态</th></tr>
      </thead>
      <tbody>
{rows}
      </tbody>
    </table>
    <div class="total">
      已出分 {summary['graded']} 门，共 {summary['credits']:g} 学分；
      加权平均分 <b>{weighted}</b>
    </div>
    <div class="actions"><button onclick="window.print()">打印</button></div>
  </div>
</body>
</html>
"""


def write_transcript_html(cfg, student_id: int, path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(transcript_html(cfg, student_id), encoding="utf-8")
    return target
