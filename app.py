"""班级作业管理系统。

运行方式：streamlit run app.py
页面每次交互都会从上到下重新执行；登录用户通过 st.session_state 保存。
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

# 将数据库和上传文件固定在本程序所在的目录，避免受启动位置影响。
APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "classwork.db"
UPLOAD_DIR = APP_DIR / "uploads"


def password_hash(value: str) -> str:
    """把明文密码转换成不可逆摘要，数据库只保存摘要而非原密码。"""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def db() -> sqlite3.Connection:
    """创建一个已启用外键约束的 SQLite 连接。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """首次运行时创建上传目录、数据表和默认管理员账号。"""
    UPLOAD_DIR.mkdir(exist_ok=True)
    with db() as conn:
        conn.executescript(
            """
            -- users：管理员和学生；assignments：作业；submissions：提交记录；notifications：班级通知。
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'student')),
                student_no TEXT UNIQUE,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                title TEXT NOT NULL,
                requirements TEXT NOT NULL,
                deadline TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                saved_path TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                is_late INTEGER NOT NULL,
                -- 同一学生对同一作业只能有一条记录；再次提交会改为更新该记录。
                UNIQUE(assignment_id, student_id),
                FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
                FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        exists = conn.execute("SELECT 1 FROM users WHERE username='admin'").fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO users (username,password_hash,role,student_no,display_name,created_at) VALUES (?,?,?,?,?,?)",
                ("admin", password_hash("admin123"), "admin", None, "学习委员", now()),
            )


def now() -> str:
    """返回统一格式的当前时间，便于存入 SQLite 并用于比较。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """执行只读查询；问号占位符会安全地绑定 params 中的值。"""
    with db() as conn:
        return conn.execute(sql, params).fetchall()


def excel_file(frame: pd.DataFrame, sheet_name: str) -> bytes:
    """将 DataFrame 暂存在内存中并转换为可下载的 Excel 字节数据。"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return output.getvalue()


def login_page() -> None:
    st.title("班级作业管理系统")
    st.caption("登录后，管理员负责发布与统计；学生只需查看并提交作业。")
    with st.form("login"):
        username = st.text_input("账号")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录", use_container_width=True)
    if submitted:
        # 账号和密码摘要均匹配才算登录成功。
        row = query("SELECT * FROM users WHERE username=? AND password_hash=?", (username.strip(), password_hash(password)) )
        if row:
            # session_state 在 Streamlit 的重复运行之间保留当前登录用户。
            st.session_state.user = dict(row[0])
            st.rerun()
        else:
            st.error("账号或密码不正确")
    st.info("首次使用管理员账号：admin；初始密码：admin123。请登录后立即修改。")


def logout_button() -> None:
    if st.sidebar.button("退出登录"):
        st.session_state.pop("user", None)
        st.rerun()


def change_password(user: dict) -> None:
    with st.expander("修改我的密码"):
        with st.form("change_password"):
            old = st.text_input("当前密码", type="password")
            new = st.text_input("新密码（至少 6 位）", type="password")
            ok = st.form_submit_button("保存新密码")
        if ok:
            if len(new) < 6:
                st.error("新密码至少 6 位")
            elif password_hash(old) != user["password_hash"]:
                st.error("当前密码不正确")
            else:
                # with 结束时自动提交；发生异常时会回滚。
                with db() as conn:
                    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash(new), user["id"]))
                st.success("密码已修改")


def admin_publish() -> None:
    st.header("发布作业")
    with st.form("publish", clear_on_submit=True):
        subject = st.text_input("科目 *", placeholder="例如：高等数学")
        title = st.text_input("作业标题 *", placeholder="例如：第三章习题")
        requirements = st.text_area("作业要求 *", placeholder="写清题目范围、格式和提交说明")
        deadline = st.datetime_input("截止时间 *", value=datetime.now())
        ok = st.form_submit_button("发布作业", use_container_width=True)
    if ok:
        if not all([subject.strip(), title.strip(), requirements.strip()]):
            st.error("请填写所有必填项")
        else:
            with db() as conn:
                conn.execute("INSERT INTO assignments (subject,title,requirements,deadline,created_at) VALUES (?,?,?,?,?)",
                             (subject.strip(), title.strip(), requirements.strip(), deadline.strftime("%Y-%m-%d %H:%M:%S"), now()))
            st.success("作业已发布。把系统链接发到班群即可。")

    st.divider()
    st.subheader("已发布作业")
    assignments = query("SELECT * FROM assignments ORDER BY deadline DESC")
    if not assignments:
        st.caption("暂未发布作业。")
        return

    published = pd.DataFrame(
        [{"科目": a["subject"], "标题": a["title"], "截止时间": a["deadline"]} for a in assignments]
    )
    st.dataframe(published, use_container_width=True, hide_index=True)

    with st.expander("删除已发布作业"):
        st.warning("删除后，该作业的全部提交记录和已上传文件也会一并删除，无法恢复。")
        options = {f"[{a['subject']}] {a['title']}（截止 {a['deadline']}）": a for a in assignments}
        selected = options[st.selectbox("选择要删除的作业", list(options), key="delete_assignment_select")]
        confirmed = st.checkbox("我确认删除此作业及其所有提交文件", key="delete_assignment_confirm")
        if st.button("永久删除作业", type="primary", disabled=not confirmed):
            delete_assignment(selected["id"])
            st.success("作业及关联提交已删除。")
            st.rerun()


def delete_assignment(assignment_id: int) -> None:
    """删除作业、提交记录与仅位于 uploads 目录内的关联文件。"""
    submissions = query("SELECT saved_path FROM submissions WHERE assignment_id=?", (assignment_id,))
    with db() as conn:
        # submissions 的外键 ON DELETE CASCADE 会同步删除该作业的提交记录。
        conn.execute("DELETE FROM assignments WHERE id=?", (assignment_id,))

    uploads_root = UPLOAD_DIR.resolve()
    for submission in submissions:
        file_path = (APP_DIR / submission["saved_path"]).resolve()
        # 数据库内容即使被意外修改，也绝不删除 uploads 文件夹之外的文件。
        if uploads_root in file_path.parents and file_path.is_file():
            file_path.unlink()


def admin_notifications() -> None:
    st.header("发布通知")
    st.caption("通知会在所有学生首页的“通知”栏目中显示。重要通知仍建议将系统链接或截图发到班群。")
    with st.form("publish_notification", clear_on_submit=True):
        title = st.text_input("通知标题 *", placeholder="例如：明天课程调整")
        content = st.text_area("通知内容 *", placeholder="请写清具体事项、时间和地点")
        ok = st.form_submit_button("发布通知", use_container_width=True)
    if ok:
        if not title.strip() or not content.strip():
            st.error("请填写通知标题和内容")
        else:
            with db() as conn:
                conn.execute("INSERT INTO notifications (title,content,created_at) VALUES (?,?,?)",
                             (title.strip(), content.strip(), now()))
            st.success("通知已发布。")

    st.subheader("已发布通知")
    notifications = query("SELECT title AS 标题, content AS 内容, created_at AS 发布时间 FROM notifications ORDER BY created_at DESC")
    if notifications:
        st.dataframe(pd.DataFrame(notifications), use_container_width=True, hide_index=True)
    else:
        st.caption("暂未发布通知。")


def admin_students() -> None:
    st.header("学生管理")
    with st.form("add_student", clear_on_submit=True):
        a, b, c = st.columns(3)
        no = a.text_input("学号 *")
        name = b.text_input("姓名 *")
        pwd = c.text_input("初始密码 *", type="password")
        ok = st.form_submit_button("添加学生")
    if ok:
        if not all([no.strip(), name.strip(), pwd]) or len(pwd) < 6:
            st.error("学号、姓名必填，初始密码至少 6 位")
        else:
            try:
                with db() as conn:
                    conn.execute("INSERT INTO users (username,password_hash,role,student_no,display_name,created_at) VALUES (?,?,?,?,?,?)",
                                 (no.strip(), password_hash(pwd), "student", no.strip(), name.strip(), now()))
                st.success(f"已添加 {name.strip()}，登录账号为学号。")
            except sqlite3.IntegrityError:
                st.error("该学号已存在")
    students = query("SELECT id, student_no, display_name, created_at FROM users WHERE role='student' ORDER BY student_no")
    student_table = pd.DataFrame(
        [{"学号": s["student_no"], "姓名": s["display_name"], "创建时间": s["created_at"]} for s in students]
    )
    st.dataframe(student_table, use_container_width=True, hide_index=True)

    if students:
        with st.expander("删除已添加学生"):
            st.warning("删除后，该学生的账号、提交记录和已上传文件都会被永久删除，无法恢复。")
            options = {f"{s['display_name']}（{s['student_no']}）": s for s in students}
            selected = options[st.selectbox("选择要删除的学生", list(options), key="delete_student_select")]
            confirmed = st.checkbox("我确认删除该学生及其所有提交文件", key="delete_student_confirm")
            if st.button("永久删除学生", type="primary", disabled=not confirmed):
                delete_student(selected["id"])
                st.success("学生账号及关联提交已删除。")
                st.rerun()


def delete_student(student_id: int) -> None:
    """删除学生、提交记录与仅位于 uploads 目录内的关联文件。"""
    submissions = query("SELECT saved_path FROM submissions WHERE student_id=?", (student_id,))
    with db() as conn:
        # submissions 的外键 ON DELETE CASCADE 会同步删除该学生的提交记录。
        conn.execute("DELETE FROM users WHERE id=? AND role='student'", (student_id,))

    uploads_root = UPLOAD_DIR.resolve()
    for submission in submissions:
        file_path = (APP_DIR / submission["saved_path"]).resolve()
        # 数据库内容即使被意外修改，也绝不删除 uploads 文件夹之外的文件。
        if uploads_root in file_path.parents and file_path.is_file():
            file_path.unlink()


def assignment_picker(label: str = "选择作业") -> sqlite3.Row | None:
    assignments = query("SELECT * FROM assignments ORDER BY deadline DESC")
    if not assignments:
        st.info("还没有作业，请先发布。")
        return None
    # 下拉框显示易读文字，实际返回对应的数据库记录。
    mapping = {f"[{a['subject']}] {a['title']}（截止 {a['deadline']}）": a for a in assignments}
    return mapping[st.selectbox(label, list(mapping))]


def admin_remind_export() -> None:
    st.header("催交与导出")
    assignment = assignment_picker()
    if not assignment:
        return
    # NOT EXISTS 表示：找出不存在该作业提交记录的学生，即未交学生。
    rows = query("""SELECT u.student_no, u.display_name FROM users u
                    WHERE u.role='student' AND NOT EXISTS
                    (SELECT 1 FROM submissions s WHERE s.student_id=u.id AND s.assignment_id=?)
                    ORDER BY u.student_no""", (assignment["id"],))
    missing = pd.DataFrame(rows, columns=["学号", "姓名"])
    st.subheader(f"未交名单（{len(missing)} 人）")
    st.dataframe(missing, use_container_width=True, hide_index=True)
    names = "、".join(f"{r['display_name']}（{r['student_no']}）" for r in rows) or "无，所有同学均已提交。"
    message = f"【作业催交】{assignment['subject']}《{assignment['title']}》截止时间：{assignment['deadline']}。未提交：{names}"
    st.text_area("可直接复制到班群", message, height=120)
    st.download_button("下载未交名单 Excel", excel_file(missing, "未交名单"), "未交名单.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # CROSS JOIN 先生成“每份作业 × 每位学生”的完整组合，再拼接实际提交记录。
    summary = pd.DataFrame(query("""SELECT a.subject AS 科目, a.title AS 作业, a.deadline AS 截止时间,
        u.student_no AS 学号, u.display_name AS 姓名, COALESCE(s.submitted_at, '') AS 提交时间,
        CASE WHEN s.id IS NULL THEN '未交' WHEN s.is_late=1 THEN '迟交' ELSE '按时提交' END AS 状态,
        COALESCE(s.filename, '') AS 文件名
        FROM assignments a CROSS JOIN users u LEFT JOIN submissions s ON s.assignment_id=a.id AND s.student_id=u.id
        WHERE u.role='student' ORDER BY a.deadline DESC, u.student_no"""))
    st.download_button("下载全部提交汇总 Excel", excel_file(summary, "提交汇总"), "作业提交汇总.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def admin_board() -> None:
    st.header("提交看板")
    students = query("SELECT id, student_no, display_name FROM users WHERE role='student' ORDER BY student_no")
    assignments = query("SELECT id, subject, title FROM assignments ORDER BY deadline")
    if not students or not assignments:
        st.info("看板需要至少一名学生和一份作业。")
        return
    # 字典用 (作业 ID, 学生 ID) 作键，可快速查询每个格子的提交状态。
    submitted = {(r["assignment_id"], r["student_id"]): "迟交" if r["is_late"] else "已交" for r in query("SELECT assignment_id,student_id,is_late FROM submissions")}
    data = []
    for a in assignments:
        row = {"作业": f"{a['subject']}｜{a['title']}"}
        for s in students:
            row[f"{s['display_name']}\n{s['student_no']}"] = submitted.get((a["id"], s["id"]), "未交")
        data.append(row)
    board = pd.DataFrame(data)
    st.caption("红色为未交；黄色为迟交。")
    st.dataframe(board.style.map(lambda v: "background-color:#ffc7ce;color:#9c0006" if v == "未交" else "background-color:#ffeb9c" if v == "迟交" else "", subset=board.columns[1:]), use_container_width=True, hide_index=True)


def student_assignments(user: dict) -> None:
    st.header("我的作业")
    # LEFT JOIN 保留所有作业，即使该学生尚未提交也能显示“未交”。
    rows = query("""SELECT a.*, s.submitted_at, s.is_late, s.filename FROM assignments a
        LEFT JOIN submissions s ON s.assignment_id=a.id AND s.student_id=? ORDER BY a.deadline ASC""", (user["id"],))
    if not rows:
        st.info("老师暂未发布作业。")
        return
    for a in rows:
        status = "🟢 已交" if a["submitted_at"] else "🔴 未交"
        if a["submitted_at"] and a["is_late"]:
            status = "🟡 已交（迟交）"
        with st.expander(f"{status}｜{a['subject']}｜{a['title']}｜截止 {a['deadline']}", expanded=not bool(a["submitted_at"])):
            st.write(a["requirements"])
            if a["submitted_at"]:
                st.caption(f"最近提交：{a['submitted_at']}；文件：{a['filename']}")
            uploaded = st.file_uploader("选择文件", key=f"upload_{a['id']}")
            if st.button("提交 / 更新文件", key=f"submit_{a['id']}", disabled=uploaded is None):
                save_submission(a, user, uploaded)


def student_notifications() -> None:
    """展示全体学生均可见的班级通知。"""
    st.header("班级通知")
    notifications = query("SELECT * FROM notifications ORDER BY created_at DESC")
    if not notifications:
        st.info("暂时没有新通知。")
        return
    for notice in notifications:
        with st.expander(f"📢 {notice['title']}｜发布于 {notice['created_at']}", expanded=True):
            st.write(notice["content"])


def student_home(user: dict) -> None:
    """学生端将待办作业与班级通知分成独立栏目。"""
    assignments_tab, notifications_tab = st.tabs(["作业", "通知"])
    with assignments_tab:
        student_assignments(user)
    with notifications_tab:
        student_notifications()


def save_submission(assignment: sqlite3.Row, user: dict, uploaded) -> None:
    """保存上传文件，并新增或更新该学生对当前作业的提交记录。"""
    original = Path(uploaded.name).name
    # 仅保留安全字符，防止上传文件名中带有不适合做路径的字符。
    safe_original = re.sub(r"[^\w.\-()\u4e00-\u9fff]", "_", original)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{user['student_no']}_{stamp}_{safe_original}"
    target = UPLOAD_DIR / filename
    target.write_bytes(uploaded.getbuffer())
    submitted_at = now()
    # bool 转为 0/1，正好可以存入 SQLite 的 INTEGER 字段。
    late = int(datetime.strptime(submitted_at, "%Y-%m-%d %H:%M:%S") > datetime.strptime(assignment["deadline"], "%Y-%m-%d %H:%M:%S"))
    with db() as conn:
        conn.execute("""INSERT INTO submissions (assignment_id,student_id,filename,saved_path,submitted_at,is_late)
            -- UNIQUE 冲突时更新旧提交，实现“重新提交”。
            VALUES (?,?,?,?,?,?) ON CONFLICT(assignment_id,student_id) DO UPDATE SET
            filename=excluded.filename,saved_path=excluded.saved_path,submitted_at=excluded.submitted_at,is_late=excluded.is_late""",
            (assignment["id"], user["id"], filename, str(target.relative_to(APP_DIR)), submitted_at, late))
    st.success("提交成功" + "（已标记为迟交）" if late else "提交成功")
    st.rerun()


def app() -> None:
    """应用入口：初始化数据后，根据角色渲染管理员或学生页面。"""
    st.set_page_config(page_title="班级作业管理系统", page_icon="📚", layout="wide")
    init_db()
    if "user" not in st.session_state:
        login_page()
        return
    user = st.session_state.user
    st.sidebar.title(f"你好，{user['display_name']}")
    if user["role"] == "admin":
        page = st.sidebar.radio("功能", ["发布作业", "发布通知", "提交看板", "催交与导出", "学生管理"])
        # 字典把页面名称映射到函数；取出后立刻用 () 调用。
        {"发布作业": admin_publish, "发布通知": admin_notifications, "提交看板": admin_board, "催交与导出": admin_remind_export, "学生管理": admin_students}[page]()
    else:
        student_home(user)
    change_password(user)
    logout_button()


if __name__ == "__main__":
    # 只有直接运行此文件时才启动应用；被其他文件导入时不会自动执行。
    app()
