PRAGMA foreign_keys = ON;

BEGIN;

DROP VIEW  IF EXISTS v_student_score;
DROP VIEW  IF EXISTS v_course_stats;
DROP VIEW  IF EXISTS v_student_avg;
DROP TABLE IF EXISTS scores;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS classes;

CREATE TABLE classes (
    class_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name   TEXT    NOT NULL UNIQUE,
    major        TEXT    NOT NULL,
    grade        INTEGER NOT NULL CHECK (grade BETWEEN 2000 AND 2100),
    head_teacher TEXT
);

CREATE TABLE students (
    student_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    sno         TEXT    NOT NULL UNIQUE CHECK (length(sno) BETWEEN 4 AND 20),
    name        TEXT    NOT NULL CHECK (length(trim(name)) > 0),
    gender      TEXT    NOT NULL CHECK (gender IN ('男', '女')),
    birthday    TEXT,
    phone       TEXT,
    email       TEXT,
    class_id    INTEGER,
    enroll_date TEXT    NOT NULL DEFAULT (date('now', 'localtime')),
    FOREIGN KEY (class_id) REFERENCES classes (class_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE TABLE courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cno       TEXT    NOT NULL UNIQUE,
    title     TEXT    NOT NULL,
    credit    REAL    NOT NULL DEFAULT 2.0 CHECK (credit > 0),
    teacher   TEXT,
    hours     INTEGER NOT NULL DEFAULT 32 CHECK (hours > 0)
);

CREATE TABLE scores (
    student_id INTEGER NOT NULL,
    course_id  INTEGER NOT NULL,
    term       TEXT    NOT NULL,
    score      REAL    CHECK (score IS NULL OR (score >= 0 AND score <= 100)),
    updated_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    PRIMARY KEY (student_id, course_id, term),
    FOREIGN KEY (student_id) REFERENCES students (student_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses (course_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX idx_students_class ON students (class_id);
CREATE INDEX idx_students_name  ON students (name);
CREATE INDEX idx_scores_course  ON scores  (course_id);

CREATE VIEW v_student_score AS
SELECT sc.rowid      AS score_id,
       s.sno         AS sno,
       s.name        AS name,
       c.class_name  AS class_name,
       co.title      AS course,
       co.credit     AS credit,
       sc.term       AS term,
       sc.score      AS score,
       CASE WHEN sc.score IS NULL  THEN '未录入'
            WHEN sc.score >= 60    THEN '及格'
            ELSE '不及格' END      AS pass_state
FROM scores sc
JOIN students s ON s.student_id = sc.student_id
JOIN courses  co ON co.course_id = sc.course_id
LEFT JOIN classes c ON c.class_id = s.class_id;

CREATE VIEW v_course_stats AS
SELECT co.cno            AS cno,
       co.title          AS course,
       COUNT(sc.score)   AS graded,
       ROUND(AVG(sc.score), 2) AS avg_score,
       MAX(sc.score)     AS max_score,
       MIN(sc.score)     AS min_score,
       ROUND(100.0 * SUM(CASE WHEN sc.score >= 60 THEN 1 ELSE 0 END)
             / NULLIF(COUNT(sc.score), 0), 1) AS pass_rate
FROM courses co
LEFT JOIN scores sc ON sc.course_id = co.course_id
GROUP BY co.course_id;

CREATE VIEW v_student_avg AS
SELECT s.student_id AS student_id,
       s.sno        AS sno,
       s.name       AS name,
       c.class_name AS class_name,
       COUNT(sc.score) AS graded,
       SUM(CASE WHEN sc.score IS NOT NULL THEN co.credit ELSE 0 END) AS credits,
       ROUND(SUM(sc.score * co.credit)
             / NULLIF(SUM(CASE WHEN sc.score IS NOT NULL THEN co.credit END), 0), 2) AS weighted_avg
FROM students s
LEFT JOIN classes c  ON c.class_id  = s.class_id
LEFT JOIN scores  sc ON sc.student_id = s.student_id
LEFT JOIN courses co ON co.course_id  = sc.course_id
GROUP BY s.student_id;

CREATE TRIGGER trg_scores_touch
AFTER UPDATE OF score ON scores
FOR EACH ROW
BEGIN
    UPDATE scores
       SET updated_at = datetime('now', 'localtime')
     WHERE student_id = NEW.student_id
       AND course_id  = NEW.course_id
       AND term       = NEW.term;
END;

COMMIT;
