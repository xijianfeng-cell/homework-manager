"""班级作业管理系统（Streamlit + Supabase PostgreSQL）。"""

from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from supabase import create_client
from werkzeug.security import check_password_hash, generate_password_hash

STORAGE_BUCKET = "homework-files"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def password_hash(value: str) -> str:
    return generate_password_hash(value)


@st.cache_resource
def supabase_client():
    """创建并缓存 Supabase 客户端。"""
    try:
        url = str(st.secrets["SUPABASE_URL"]).strip()
        key = str(st.secrets["SUPABASE_SERVICE_ROLE_KEY"]).strip()
    except KeyError:
        st.error(
            "缺少 Supabase 配置。请检查 Streamlit Secrets。"
        )
        st.stop()

    try:
        key.encode("ascii")
    except UnicodeEncodeError:
        st.error(
            "SUPABASE_SERVICE_ROLE_KEY 含有中文或全角符号，"
            "请重新复制 Supabase Secret Key。"
        )
        st.stop()

    if not url.startswith("https://") or ".supabase.co" not in url:
        st.error("SUPABASE_URL 格式不正确。")
        st.stop()

    return create_client(url, key)


def rows(table: str, *, order: str | None = None, desc: bool = False) -> list[dict]:
    request = supabase_client().table(table).select("*")
    if order:
        request = request.order(order, desc=desc)
    return request.execute().data


def first(table: str, **filters) -> dict | None:
    request = supabase_client().table(table).select("*")
    for column, value in filters.items():
        request = request.eq(column, value)
    data = request.limit(1).execute().data
    return data[0] if data else None


def insert(table: str, data: dict) -> dict:
    return supabase_client().table(table).insert(data).execute().data[0]


def init_db() -> None:
    """Supabase 建表由 supabase_schema.sql 完成；这里仅初始化管理员。"""
    if not first("users", username="admin"):
        insert("users", {"username": "admin", "password_hash": password_hash("admin123"), "role": "admin", "display_name": "学习委员", "created_at": now()})


def excel_file(frame: pd.DataFrame, sheet_name: str) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return output.getvalue()


def login_page() -> None:
    st.title("班级作业管理系统")
    st.caption("管理员负责发布与统计；学生只需查看并提交作业。")
    with st.form("login"):
        username = st.text_input("账号")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录", use_container_width=True)
    if submitted:
        user = first("users", username=username.strip())
        if user and check_password_hash(user["password_hash"], password):
            st.session_state.user = user
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
            elif not check_password_hash(user["password_hash"], old):
                st.error("当前密码不正确")
            else:
                hashed = password_hash(new)
                supabase_client().table("users").update({"password_hash": hashed}).eq("id", user["id"]).execute()
                st.session_state.user["password_hash"] = hashed
                st.success("密码已修改")

# def delete_notification(notification_id: int) -> None:
#     supabase_client().table("notifications").delete().eq(
#         "id", notification_id
#     ).execute()


# def admin_notifications() -> None:
#     st.header("发布通知")
#     st.caption(
#         "通知会在所有学生首页的“通知”栏目中显示。"
#         "重要通知仍建议将系统链接或截图发到班群。"
#     )

#     # 发布通知
#     with st.form("publish_notification", clear_on_submit=True):
#         title = st.text_input(
#             "通知标题 *",
#             placeholder="例如：明天课程调整"
#         )
#         content = st.text_area(
#             "通知内容 *",
#             placeholder="请写清具体事项、时间和地点"
#         )
#         ok = st.form_submit_button(
#             "发布通知",
#             use_container_width=True
#         )

#     if ok:
#         if not title.strip() or not content.strip():
#             st.error("请填写通知标题和内容")
#         else:
#             insert(
#                 "notifications",
#                 {
#                     "title": title.strip(),
#                     "content": content.strip(),
#                     "created_at": now()
#                 }
#             )
#             st.success("通知已发布。")
#             st.rerun()

#     # 已发布通知
#     notices = rows("notifications", order="created_at", desc=True)

#     if notices:
#         st.subheader("已发布通知")

#         st.dataframe(
#             pd.DataFrame([
#                 {
#                     "标题": n["title"],
#                     "内容": n["content"],
#                     "发布时间": n["created_at"]
#                 }
#                 for n in notices
#             ]),
#             use_container_width=True,
#             hide_index=True
#         )

#         # 删除通知
#         st.subheader("删除通知")

#         choices = {
#             f"{n['title']}（{n['created_at']}）": n
#             for n in notices
#         }

#         selected = choices[
#             st.selectbox(
#                 "选择要删除的通知",
#                 list(choices),
#                 key="delete_notification_select"
#             )
#         ]

#         confirmed = st.checkbox(
#             "我确认删除这条通知",
#             key="delete_notification_confirm"
#         )

#         if st.button(
#             "永久删除通知",
#             type="primary",
#             disabled=not confirmed
#         ):
#             delete_notification(selected["id"])
#             st.success("通知已删除。")
#             st.rerun()

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
            insert("assignments", {"subject": subject.strip(), "title": title.strip(), "requirements": requirements.strip(), "deadline": deadline.strftime("%Y-%m-%d %H:%M:%S"), "created_at": now()})
            st.success("作业已发布。把系统链接发到班群即可。")
    st.divider()
    st.subheader("已发布作业")
    assignments = rows("assignments", order="deadline", desc=True)
    if not assignments:
        st.caption("暂未发布作业。")
        return
    st.dataframe(pd.DataFrame([{"科目": a["subject"], "标题": a["title"], "截止时间": a["deadline"]} for a in assignments]), use_container_width=True, hide_index=True)
    with st.expander("删除已发布作业"):
        st.warning("删除后，该作业的全部提交记录和已上传文件也会一并删除，无法恢复。")
        choices = {f"[{a['subject']}] {a['title']}（截止 {a['deadline']}）": a for a in assignments}
        selected = choices[st.selectbox("选择要删除的作业", list(choices), key="delete_assignment_select")]
        confirmed = st.checkbox("我确认删除此作业及其所有提交文件", key="delete_assignment_confirm")
        if st.button("永久删除作业", type="primary", disabled=not confirmed):
            delete_assignment(selected["id"])
            st.success("作业及关联提交已删除。")
            st.rerun()


def remove_submission_files(submissions: list[dict]) -> None:
    """删除 Supabase Storage 中的附件；空路径或已不存在的附件直接忽略。"""
    paths = [submission["saved_path"] for submission in submissions if submission.get("saved_path")]
    if paths:
        supabase_client().storage.from_(STORAGE_BUCKET).remove(paths)

def download_submission_file(saved_path: str) -> bytes:
    """从 Supabase Storage 读取学生提交的文件。"""
    return (
        supabase_client()
        .storage
        .from_(STORAGE_BUCKET)
        .download(saved_path)
    )

def delete_assignment(assignment_id: int) -> None:
    submitted = supabase_client().table("submissions").select("saved_path").eq("assignment_id", assignment_id).execute().data
    remove_submission_files(submitted)
    supabase_client().table("assignments").delete().eq("id", assignment_id).execute()


# def admin_notifications() -> None:
#     st.header("发布通知")
#     st.caption("通知会在所有学生首页的“通知”栏目中显示。重要通知仍建议将系统链接或截图发到班群。")
#     with st.form("publish_notification", clear_on_submit=True):
#         title = st.text_input("通知标题 *", placeholder="例如：明天课程调整")
#         content = st.text_area("通知内容 *", placeholder="请写清具体事项、时间和地点")
#         ok = st.form_submit_button("发布通知", use_container_width=True)
#     if ok:
#         if not title.strip() or not content.strip():
#             st.error("请填写通知标题和内容")
#         else:
#             insert("notifications", {"title": title.strip(), "content": content.strip(), "created_at": now()})
#             st.success("通知已发布。")
#     notices = rows("notifications", order="created_at", desc=True)
#     if notices:
#         st.subheader("已发布通知")
#         st.dataframe(pd.DataFrame([{"标题": n["title"], "内容": n["content"], "发布时间": n["created_at"]} for n in notices]), use_container_width=True, hide_index=True)
def delete_notification(notification_id: int) -> None:
    supabase_client().table("notifications").delete().eq(
        "id", notification_id
    ).execute()


def admin_notifications() -> None:
    st.header("发布通知")
    st.caption(
        "通知会在所有学生首页的“通知”栏目中显示。"
        "重要通知仍建议将系统链接或截图发到班群。"
    )

    # 发布通知
    with st.form("publish_notification", clear_on_submit=True):
        title = st.text_input(
            "通知标题 *",
            placeholder="例如：明天课程调整"
        )
        content = st.text_area(
            "通知内容 *",
            placeholder="请写清具体事项、时间和地点"
        )
        ok = st.form_submit_button(
            "发布通知",
            use_container_width=True
        )

    if ok:
        if not title.strip() or not content.strip():
            st.error("请填写通知标题和内容")
        else:
            insert(
                "notifications",
                {
                    "title": title.strip(),
                    "content": content.strip(),
                    "created_at": now()
                }
            )
            st.success("通知已发布。")
            st.rerun()

    # 已发布通知
    notices = rows("notifications", order="created_at", desc=True)

    if notices:
        st.subheader("已发布通知")

        st.dataframe(
            pd.DataFrame([
                {
                    "标题": n["title"],
                    "内容": n["content"],
                    "发布时间": n["created_at"]
                }
                for n in notices
            ]),
            use_container_width=True,
            hide_index=True
        )

        # 删除通知
        st.subheader("删除通知")

        choices = {
            f"{n['title']}（{n['created_at']}）": n
            for n in notices
        }

        selected = choices[
            st.selectbox(
                "选择要删除的通知",
                list(choices),
                key="delete_notification_select"
            )
        ]

        confirmed = st.checkbox(
            "我确认删除这条通知",
            key="delete_notification_confirm"
        )

        if st.button(
            "永久删除通知",
            type="primary",
            disabled=not confirmed
        ):
            delete_notification(selected["id"])
            st.success("通知已删除。")
            st.rerun()

def admin_students() -> None:
    st.header("学生管理")
    with st.form("add_student", clear_on_submit=True):
        a, b, c = st.columns(3)
        number = a.text_input("学号 *")
        name = b.text_input("姓名 *")
        pwd = c.text_input("初始密码 *", type="password")
        ok = st.form_submit_button("添加学生")
    if ok:
        if not all([number.strip(), name.strip(), pwd]) or len(pwd) < 6:
            st.error("学号、姓名必填，初始密码至少 6 位")
        else:
            try:
                insert("users", {"username": number.strip(), "password_hash": password_hash(pwd), "role": "student", "student_no": number.strip(), "display_name": name.strip(), "created_at": now()})
                st.success(f"已添加 {name.strip()}，登录账号为学号。")
            except Exception:
                st.error("该学号已存在")
    students = [u for u in rows("users", order="student_no") if u["role"] == "student"]
    st.dataframe(pd.DataFrame([{"学号": s["student_no"], "姓名": s["display_name"], "创建时间": s["created_at"]} for s in students]), use_container_width=True, hide_index=True)
    if students:
        with st.expander("删除已添加学生"):
            st.warning("删除后，该学生的账号、提交记录和已上传文件都会被永久删除，无法恢复。")
            choices = {f"{s['display_name']}（{s['student_no']}）": s for s in students}
            selected = choices[st.selectbox("选择要删除的学生", list(choices), key="delete_student_select")]
            confirmed = st.checkbox("我确认删除该学生及其所有提交文件", key="delete_student_confirm")
            if st.button("永久删除学生", type="primary", disabled=not confirmed):
                delete_student(selected["id"])
                st.success("学生账号及关联提交已删除。")
                st.rerun()


def delete_student(student_id: int) -> None:
    submitted = supabase_client().table("submissions").select("saved_path").eq("student_id", student_id).execute().data
    remove_submission_files(submitted)
    supabase_client().table("users").delete().eq("id", student_id).eq("role", "student").execute()


def assignment_picker() -> dict | None:
    assignments = rows("assignments", order="deadline", desc=True)
    if not assignments:
        st.info("还没有作业，请先发布。")
        return None
    choices = {f"[{a['subject']}] {a['title']}（截止 {a['deadline']}）": a for a in assignments}
    return choices[st.selectbox("选择作业", list(choices))]


def submission_summary() -> pd.DataFrame:
    students = [u for u in rows("users", order="student_no") if u["role"] == "student"]
    assignments = rows("assignments", order="deadline", desc=True)
    submission_map = {(s["assignment_id"], s["student_id"]): s for s in rows("submissions")}
    data = []
    for assignment in assignments:
        for student in students:
            item = submission_map.get((assignment["id"], student["id"]))
            data.append({"科目": assignment["subject"], "作业": assignment["title"], "截止时间": assignment["deadline"], "学号": student["student_no"], "姓名": student["display_name"], "提交时间": item["submitted_at"] if item else "", "状态": "未交" if not item else "迟交" if item["is_late"] else "按时提交", "文件名": item["filename"] if item else ""})
    return pd.DataFrame(data)


def admin_remind_export() -> None:
    st.header("催交与导出")
    assignment = assignment_picker()
    if not assignment:
        return
    students = [u for u in rows("users", order="student_no") if u["role"] == "student"]
    submitted = supabase_client().table("submissions").select("student_id").eq("assignment_id", assignment["id"]).execute().data
    submitted_ids = {s["student_id"] for s in submitted}
    missing_rows = [{"学号": s["student_no"], "姓名": s["display_name"]} for s in students if s["id"] not in submitted_ids]
    missing = pd.DataFrame(missing_rows, columns=["学号", "姓名"])
    st.subheader(f"未交名单（{len(missing)} 人）")
    st.dataframe(missing, use_container_width=True, hide_index=True)
    names = "、".join(f"{r['姓名']}（{r['学号']}）" for r in missing_rows) or "无，所有同学均已提交。"
    st.text_area("可直接复制到班群", f"【作业催交】{assignment['subject']}《{assignment['title']}》截止时间：{assignment['deadline']}。未提交：{names}", height=120)
    st.download_button("下载未交名单 Excel", excel_file(missing, "未交名单"), "未交名单.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("下载全部提交汇总 Excel", excel_file(submission_summary(), "提交汇总"), "作业提交汇总.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# def admin_board() -> None:
#     st.header("提交看板")
#     students = [u for u in rows("users", order="student_no") if u["role"] == "student"]
#     assignments = rows("assignments", order="deadline")
#     if not students or not assignments:
#         st.info("看板需要至少一名学生和一份作业。")
#         return
#     submitted = {(r["assignment_id"], r["student_id"]): "迟交" if r["is_late"] else "已交" for r in rows("submissions")}
#     data = []
#     for assignment in assignments:
#         row = {"作业": f"{assignment['subject']}｜{assignment['title']}"}
#         for student in students:
#             row[f"{student['display_name']}\n{student['student_no']}"] = submitted.get((assignment["id"], student["id"]), "未交")
#         data.append(row)
#     board = pd.DataFrame(data)
#     st.caption("红色为未交；黄色为迟交。")
#     st.dataframe(board.style.map(lambda value: "background-color:#ffc7ce;color:#9c0006" if value == "未交" else "background-color:#ffeb9c" if value == "迟交" else "", subset=board.columns[1:]), use_container_width=True, hide_index=True)
def admin_board() -> None:
    st.header("提交看板")

    students = [
        u for u in rows("users", order="student_no")
        if u["role"] == "student"
    ]

    assignments = rows("assignments", order="deadline")

    if not students or not assignments:
        st.info("看板需要至少一名学生和一份作业。")
        return

    # 保留原来的提交状态看板
    submitted = {
        (r["assignment_id"], r["student_id"]): r
        for r in rows("submissions")
    }

    data = []

    for assignment in assignments:
        row = {
            "作业": f"{assignment['subject']}｜{assignment['title']}"
        }

        for student in students:
            submission = submitted.get(
                (assignment["id"], student["id"])
            )

            if not submission:
                status = "未交"
            elif submission["is_late"]:
                status = "迟交"
            else:
                status = "已交"

            row[
                f"{student['display_name']}\n{student['student_no']}"
            ] = status

        data.append(row)

    board = pd.DataFrame(data)

    st.caption("红色为未交；黄色为迟交。")

    st.dataframe(
        board.style.map(
            lambda value:
                "background-color:#ffc7ce;color:#9c0006"
                if value == "未交"
                else "background-color:#ffeb9c"
                if value == "迟交"
                else "",
            subset=board.columns[1:]
        ),
        use_container_width=True,
        hide_index=True
    )

    # ==========================================
    # 学生提交文件
    # ==========================================

    st.divider()
    st.subheader("学生提交文件")

    for assignment in assignments:

        st.markdown(
            f"### {assignment['subject']}｜{assignment['title']}"
        )

        assignment_submissions = [
            submission
            for submission in submitted.values()
            if submission["assignment_id"] == assignment["id"]
        ]

        if not assignment_submissions:
            st.caption("目前还没有学生提交。")
            continue

        for submission in assignment_submissions:

            student = next(
                (
                    s for s in students
                    if s["id"] == submission["student_id"]
                ),
                None
            )

            if not student:
                continue

            col1, col2, col3, col4 = st.columns(
                [1.5, 1.5, 3, 1]
            )

            with col1:
                st.write(student["display_name"])

            with col2:
                st.write(student["student_no"])

            with col3:
                st.write(submission["filename"])

            with col4:

                try:
                    file_data = download_submission_file(
                        submission["saved_path"]
                    )

                    st.download_button(
                        label="下载文件",
                        data=file_data,
                        file_name=submission["filename"],
                        key=f"download_{assignment['id']}_{student['id']}",
                        use_container_width=True
                    )

                except Exception as error:
                    st.error(f"读取失败：{error}")

def student_assignments(user: dict) -> None:
    st.header("我的作业")
    assignments = rows("assignments", order="deadline")
    own_submissions = supabase_client().table("submissions").select("*").eq("student_id", user["id"]).execute().data
    submission_map = {s["assignment_id"]: s for s in own_submissions}
    if not assignments:
        st.info("老师暂未发布作业。")
        return
    for assignment in assignments:
        submission = submission_map.get(assignment["id"])
        status = "🟢 已交" if submission else "🔴 未交"
        if submission and submission["is_late"]:
            status = "🟡 已交（迟交）"
        with st.expander(f"{status}｜{assignment['subject']}｜{assignment['title']}｜截止 {assignment['deadline']}", expanded=not bool(submission)):
            st.write(assignment["requirements"])
            if submission:
                st.caption(f"最近提交：{submission['submitted_at']}；文件：{submission['filename']}")
            uploaded = st.file_uploader("选择文件", key=f"upload_{assignment['id']}")
            if st.button("提交 / 更新文件", key=f"submit_{assignment['id']}", disabled=uploaded is None):
                save_submission(assignment, user, uploaded)


def student_notifications() -> None:
    st.header("班级通知")
    notices = rows("notifications", order="created_at", desc=True)
    if not notices:
        st.info("暂时没有新通知。")
        return
    for notice in notices:
        with st.expander(f"📢 {notice['title']}｜发布于 {notice['created_at']}", expanded=True):
            st.write(notice["content"])


def student_home(user: dict) -> None:
    assignments_tab, notifications_tab = st.tabs(["作业", "通知"])
    with assignments_tab:
        student_assignments(user)
    with notifications_tab:
        student_notifications()


def save_submission(assignment: dict, user: dict, uploaded) -> None:
    original = Path(uploaded.name).name
    safe_original = re.sub(r"[^\w.\-()\u4e00-\u9fff]", "_", original)
    filename = f"{user['student_no']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_original}"
    storage_path = f"assignments/{assignment['id']}/{user['student_no']}/{filename}"
    submitted_at = now()
    is_late = datetime.fromisoformat(submitted_at) > datetime.fromisoformat(assignment["deadline"])
    old_submission = first("submissions", assignment_id=assignment["id"], student_id=user["id"])
    try:
        supabase_client().storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=uploaded.getvalue(),
            file_options={"content-type": uploaded.type or "application/octet-stream", "upsert": "false"},
        )
        supabase_client().table("submissions").upsert({"assignment_id": assignment["id"], "student_id": user["id"], "filename": filename, "saved_path": storage_path, "submitted_at": submitted_at, "is_late": is_late}, on_conflict="assignment_id,student_id").execute()
        if old_submission and old_submission["saved_path"] != storage_path:
            remove_submission_files([old_submission])
    except Exception as error:
        # 若数据库写入失败，回收刚上传的孤立文件。
        try:
            remove_submission_files([{"saved_path": storage_path}])
        except Exception:
            pass
        st.error(f"提交失败：{error}")
        return
    st.success("提交成功（已标记为迟交）" if is_late else "提交成功")
    st.rerun()


def app() -> None:
    st.set_page_config(page_title="班级作业管理系统", page_icon="📚", layout="wide")

    if "user" not in st.session_state:
        login_page()
        return
    user = st.session_state.user
    st.sidebar.title(f"你好，{user['display_name']}")
    if user["role"] == "admin":
        page = st.sidebar.radio("功能", ["发布作业", "发布通知", "提交看板", "催交与导出", "学生管理"])
        {"发布作业": admin_publish, "发布通知": admin_notifications, "提交看板": admin_board, "催交与导出": admin_remind_export, "学生管理": admin_students}[page]()
    else:
        student_home(user)
    change_password(user)
    logout_button()



if __name__ == "__main__":
    
    app()
