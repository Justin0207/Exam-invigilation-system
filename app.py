import streamlit as st
import pandas as pd
import bcrypt
from datetime import datetime
from streamlit_calendar import calendar
from mailjet_rest import Client
from apscheduler.schedulers.background import BackgroundScheduler
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("MJ_APIKEY_PUBLIC")
api_secret = os.getenv("MJ_APIKEY_PRIVATE")


st.set_page_config(page_title="ExamInvigilate", layout="wide")


MAILJET_PUBLIC = api_key
MAILJET_PRIVATE = api_secret
FROM_EMAIL = "anyanwujustice27@gmail.com"
ADMIN_EMAIL = "anyanwuchima04@gmail.com"

def get_time_slot(time_str):
    hour = int(time_str.split(":")[0])

    if 8 <= hour < 11:
        return "8:00-11:00"
    elif 11 <= hour < 15:
        return "11:30-2:30"
    elif 15 <= hour < 19:
        return "3:00-6:00"
    else:
        return None   

def load_users():
    return pd.read_csv("users.csv")

def load_exams():
    df = pd.read_csv("exams.csv")

    # Ensure required columns exist
    for col in ["reminder_24h","reminder_6h","reminder_1h",
                "issue_reported","issue_message"]:
        if col not in df.columns:
            df[col] = False if "reminder" in col or col=="issue_reported" else ""

    if "num_students" not in df.columns:
        df["num_students"] = ""

    return df

def save_exams(df):
    df.to_csv("exams.csv", index=False)

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

# =============================
# EMAIL FUNCTIONS
# =============================
def send_email(to_email, to_name, subject, body):
    mailjet = Client(auth=(MAILJET_PUBLIC, MAILJET_PRIVATE), version='v3.1')
    data = {
        'Messages': [{
            "From": {"Email": FROM_EMAIL, "Name": "ExamInvigilate"},
            "To": [{"Email": to_email, "Name": to_name}],
            "Subject": subject,
            "TextPart": body
        }]
    }
    result = mailjet.send.create(data=data)
    return result.status_code

def send_exam_notification(to_email, to_name, course, venue, date, time, duration):
    subject = f"Exam Duty Notification - {course}"
    body = f"""
Hello {to_name},

You have been assigned to invigilate:

Course: {course}
Venue: {venue}
Date: {date}
Time: {time}
Duration: {duration}

Please log in to confirm.
"""
    return send_email(to_email, to_name, subject, body)

def send_exam_reminder(invigilator_email, invigilator_name, course, date, time, venue, duration, message_type="Reminder"):

    mailjet = Client(auth=(MAILJET_PUBLIC, MAILJET_PRIVATE), version='v3.1')

    data = {
        'Messages': [
            {
                "From": {
                    "Email": FROM_EMAIL,
                    "Name": "ExamInvigilate"
                },
                "To": [
                    {
                        "Email": invigilator_email,
                        "Name": invigilator_name
                    }
                ],
                "Subject": f"{message_type}: {course} Exam Duty",
                "TextPart": f"""
Hello {invigilator_name},

This is a friendly reminder that you are scheduled to invigilate the following exam:

Course: {course}
Venue: {venue}
Date: {date}
Time: {time}
Duration: {duration}

Please ensure you arrive at least 30 minutes before the scheduled time.

If you are unable to attend, kindly notify the admin immediately by logging into the system.

Best regards,
Exams Office   """
            }
        ]
    }

    mailjet.send.create(data=data)

def send_uncomfirmed_exams_reminder(invigilator_email, invigilator_name, course, date, time, venue, message_type="Reminder"):

    mailjet = Client(auth=(MAILJET_PUBLIC, MAILJET_PRIVATE), version='v3.1')

    data = {
        'Messages': [
            {
                "From": {
                    "Email": FROM_EMAIL,
                    "Name": "ExamInvigilate"
                },
                "To": [
                    {
                        "Email": invigilator_email,
                        "Name": invigilator_name
                    }
                ],
                "Subject": f"{message_type}: {course} Exam Duty",
                "TextPart": f"""
Dear {invigilator_name},

You are scheduled to invigilate:

Course: {course}
Venue: {venue}
Date: {date}
Time: {time}

Please confirm your duty if you have not done so.

Regards,
Exam Office
                """
            }
        ]
    }

    mailjet.send.create(data=data)

def send_admin_issue(invigilator, course, message):
    subject = f"Issue Reported - {course}"
    body = f"""
Invigilator: {invigilator}
Course: {course}

Issue:
{message}
"""
    send_email(ADMIN_EMAIL, "Admin", subject, body)

def reminder_job():
    exams = load_exams()
    users = load_users()
    now = datetime.now()

    reminder_hours = {
        "reminder_24h": 24,
        "reminder_6h": 6,
        "reminder_1h": 1
    }

    for idx, row in exams.iterrows():
        if row["status"] != "Confirmed":
            continue

        exam_datetime = datetime.strptime(
            row["date"] + " " + row["time"][:5], "%Y-%m-%d %H:%M"
        )

        hours_left = (exam_datetime - now).total_seconds() / 3600
        invigilator = users[users["id"]==row["invigilator_id"]].iloc[0]

        for col, hrs in reminder_hours.items():
            if not row[col] and 0 < hours_left <= hrs:
                send_exam_reminder(
                    invigilator["email"],
                    invigilator["name"],
                    row["course"],
                    row["date"],
                    row["time"],
                    row["venue"],
                    row["duration"]
                )
                exams.at[idx,col] = True
                save_exams(exams)

if "scheduler_started" not in st.session_state:
    scheduler = BackgroundScheduler()
    scheduler.add_job(reminder_job, 'interval', minutes=10)
    scheduler.start()
    st.session_state.scheduler_started = True


users = load_users()
exams = load_exams()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 ExamInvigilate Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = users[users["email"] == email]
        if not user.empty and verify_password(password, user.iloc[0]["password"]):
            st.session_state.logged_in = True
            st.session_state.user = user.iloc[0]
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

user = st.session_state.user

st.sidebar.write(f"Welcome {user['name']}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()
    
if user["role"] == "invigilator":

    my_exams = exams[exams["invigilator_id"] == user["id"]]

    st.title("Invigilator Dashboard")

    col1, col2, col3 = st.columns(3)
    col1.metric("Pending", len(my_exams[my_exams["status"]=="Pending"]))
    col2.metric("Confirmed", len(my_exams[my_exams["status"]=="Confirmed"]))
    col3.metric("Issues", len(my_exams[my_exams["issue_reported"]==True]))
    st.divider()

    tab1, tab2 = st.tabs(["Calendar", "Timetable"])

    with tab1:
        events = []
        for _, row in my_exams.iterrows():
            color = "green" if row["status"]=="Confirmed" else "orange"
            if row["issue_reported"]:
                color = "red"

            events.append({
                "id": row["id"],
                "title": row["course"],
                "start": f"{row['date']}T{row['time']}",
                "color": color
            })

        selected = calendar(events=events, options={"initialView":"dayGridMonth"})

        if selected and "eventClick" in selected:
            event = selected["eventClick"]["event"]
            exam_id = int(event["id"])
            row = exams[exams["id"]==exam_id].iloc[0]

            st.write("Course:", row["course"])
            st.write("Date:", row["date"]) 
            st.write("Time:", row["time"]) 
            st.write("Venue:", row["venue"])
            st.write("Duration:", row["duration"])
            st.write("Number of Students:", row["num_students"])
            st.write("Status:", row["status"])

            if row["status"]=="Pending":
                if st.button("Confirm Duty"):
                    exams.loc[exams["id"]==exam_id,"status"]="Confirmed"
                    save_exams(exams)
                    st.success("Duty Confirmed")
                    st.rerun()

            st.markdown("### Report Issue")
            issue = st.text_area("Describe issue")

            if st.button("Submit Issue"):
                exams.loc[exams["id"]==exam_id,"issue_reported"]=True
                exams.loc[exams["id"]==exam_id,"issue_message"]=issue
                exams.loc[exams["id"]==exam_id,"status"]="Issue Reported"
                save_exams(exams)

                send_admin_issue(user["name"], row["course"], issue)

                st.success("Issue reported & Admin notified!")
                st.rerun()

    # Timetable
    with tab2:

        st.subheader("Department Examination Timetable")

        all_exams = exams.copy()
    
        if all_exams.empty:
            st.warning("No exams available.")
            st.stop()
    
        all_exams["datetime"] = pd.to_datetime(
            all_exams["date"] + " " + all_exams["time"]
        )
    
        all_exams["DAY"] = all_exams["datetime"].dt.strftime("%a").str.upper()
        all_exams["DATE"] = all_exams["datetime"].dt.strftime("%d/%m/%Y")
    
        all_exams["SLOT"] = all_exams["time"].apply(get_time_slot)
    
        all_exams = all_exams.merge(
            users[["id", "name"]],
            left_on="invigilator_id",
            right_on="id",
            how="left"
        )
    
        all_exams["DISPLAY"] = (
            all_exams["course"] + " (" + all_exams["name"] + ")"
        )
    
        all_exams = all_exams[all_exams["SLOT"].notna()]
        timetable = all_exams.pivot_table(
            index=["DAY", "DATE"],
            columns="SLOT",
            values="DISPLAY",
            aggfunc=lambda x: "\n".join(x)
        ).reset_index()
        
        timetable = timetable.sort_values("DATE")
        timetable = timetable.fillna("")
        
        desired_order = ["DAY", "DATE", "8:00-11:00", "11:30-2:30", "3:00-6:00"]
        timetable = timetable[[col for col in desired_order if col in timetable.columns]]
        
        st.dataframe(timetable, width="stretch")
        csv = timetable.to_csv(index=False)
        st.download_button("⬇ Download Timetable", csv,
                            "my_exam_timetable.csv", "text/csv")
    

        sorted_exams = all_exams.sort_values("datetime")
        
        st.subheader("Course – Invigilator Assignment List")
        
        detailed = sorted_exams[[
            "course",
            "venue",
            "date",
            "time",
            "duration",
            "name",
            "num_students"
        ]].rename(columns={"name": "Invigilator", "num_students": "No. of Students"})
        
        st.dataframe(detailed, width="stretch")



# ADMIN DASHBOARD

elif user["role"] == "admin":

    st.title("Admin Dashboard")

    col1,col2,col3 = st.columns(3)
    col1.metric("Total Exams", len(exams))
    col2.metric("Confirmed", len(exams[exams["status"]=="Confirmed"]))
    col3.metric("Issues", len(exams[exams["issue_reported"]==True]))
    st.divider()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Calendar", "Assign Exam", "Timetable", "Uncomfirmed Exams Reminder", "Reminder", "Reported Issues"])

    # Calendar
    with tab1:
        events=[]
        for _, row in exams.iterrows():
            events.append({
                "id": row["id"],
                "title": row["course"],
                "start": f"{row['date']}T{row['time']}",
                "color": "blue"
            })
        selected_admin = calendar(events=events, options={"initialView":"dayGridMonth"})

        if selected_admin and "eventClick" in selected_admin:
            event = selected_admin["eventClick"]["event"]
            exam_id = int(event["id"])
            row = exams[exams["id"]==exam_id].iloc[0]

            st.write("Course:", row["course"])
            st.write("Date:", row["date"])
            st.write("Time:", row["time"])
            st.write("Venue:", row["venue"])
            st.write("Duration:", row["duration"])
            st.write("Number of Students:", row["num_students"])
            st.write("Status:", row["status"])

    # Assign Exam
    with tab2:
        course = st.text_input("Course")
        venue = st.text_input("Venue")
        date = st.date_input("Date")
        time = st.time_input("Time")
        duration = st.text_input("Duration")
        num_students = st.number_input("Number of Students", min_value=0, step=1)

        invigilators = users[users["role"]=="invigilator"]
        selected = st.selectbox("Assign To", invigilators["name"])

        if st.button("Assign"):
            inv_id = invigilators[invigilators["name"]==selected].iloc[0]["id"]

            new_exam = {
                "id": exams["id"].max()+1 if not exams.empty else 1,
                "course": course,
                "venue": venue,
                "date": str(date),
                "time": str(time)[:5],
                "duration": duration,
                "invigilator_id": inv_id,
                "status": "Pending",
                "reminder_24h": False,
                "reminder_6h": False,
                "reminder_1h": False,
                "issue_reported": False,
                "issue_message": "",
                "num_students": num_students
            }

            exams = pd.concat([exams, pd.DataFrame([new_exam])])
            save_exams(exams)

            inv_email = invigilators[invigilators["name"]==selected].iloc[0]["email"]
            send_exam_notification(inv_email, selected, course, venue, date, time, duration)

            st.success("Exam Assigned & Email Sent")
            st.rerun()

    with tab3:
        st.subheader("Department Examination Timetable")
        all_exams = exams.copy()
        if all_exams.empty:
            st.warning("No exams available.")
            st.stop()
    
        all_exams["datetime"] = pd.to_datetime(
            all_exams["date"] + " " + all_exams["time"]
        )

        all_exams["DAY"] = all_exams["datetime"].dt.strftime("%a").str.upper()
        all_exams["DATE"] = all_exams["datetime"].dt.strftime("%d/%m/%Y")
    
        all_exams["SLOT"] = all_exams["time"].apply(get_time_slot)
    
        all_exams = all_exams.merge(
            users[["id", "name"]],
            left_on="invigilator_id",
            right_on="id",
            how="left"
        )
    
        all_exams["DISPLAY"] = (
            all_exams["course"] + " (" + all_exams["name"] + ")"
        )

        all_exams = all_exams[all_exams["SLOT"].notna()]
    
        timetable = all_exams.pivot_table(
            index=["DAY", "DATE"],
            columns="SLOT",
            values="DISPLAY",
            aggfunc=lambda x: "\n".join(x)
        ).reset_index()
        timetable = timetable.sort_values("DATE")
        timetable = timetable.fillna("")
        
        desired_order = ["DAY", "DATE", "8:00-11:00", "11:30-2:30", "3:00-6:00"]
        timetable = timetable[[col for col in desired_order if col in timetable.columns]]
        
        st.dataframe(timetable, width="stretch")
    
        sorted_exams = all_exams.sort_values("datetime")
        
        st.subheader("Course – Invigilator Assignment List")
        
        detailed = sorted_exams[[
            "course",
            "venue",
            "date",
            "time",
            "duration",
            "name",
            "status",
            "num_students"
        ]].rename(columns={"name": "Invigilator", "num_students": "No. of Students"})
        
        st.dataframe(detailed, width="stretch")
        

    with tab4:
        st.subheader("Remind Unconfirmed Duties")
    
        pending_exams = all_exams[all_exams["status"] == "Pending"]
        
        if pending_exams.empty:
            st.success("No pending confirmations.")
        else:
            for index, exam in pending_exams.iterrows():
    
                col1, col2 = st.columns([4,1])
    
                with col1:
                    st.write(
                        f"{exam['course']} | {exam['date']} {exam['time']} | {exam['name']}"
                    )
    
                with col2:
                    if st.button("Send Reminder", key=f"pending_{index}"):
    
                        inv_email = users.loc[
                            users["id"] == exam["invigilator_id"], "email"
                        ].values[0]
    
                        send_uncomfirmed_exams_reminder(
                            invigilator_email=inv_email,
                            invigilator_name=exam["name"],
                            course=exam["course"],
                            date=exam["date"],
                            time=exam["time"],
                            venue=exam["venue"],
                            message_type="Confirm Your Duty"
                        )
    
                        st.success("Reminder sent successfully.")
    with tab5:
        st.subheader("Remind Upcoming Exams")
    
        now = pd.Timestamp.now()
        upcoming_window = now + pd.Timedelta(hours=24)
        
        upcoming_exams = all_exams[
            (all_exams["datetime"] > now) &
            (all_exams["datetime"] <= upcoming_window)
        ]
        
        if upcoming_exams.empty:
            st.info("No exams within next 24 hours.")
        else:
            for index, exam in upcoming_exams.iterrows():
    
                col1, col2 = st.columns([4,1])
    
                with col1:
                    st.write(
                        f"{exam['course']} | {exam['date']} {exam['time']} | {exam['name']}"
                    )
    
                with col2:
                    if st.button("Send Near-Exam Reminder", key=f"near_{index}"):
    
                        inv_email = users.loc[
                            users["id"] == exam["invigilator_id"], "email"
                        ].values[0]
    
                        send_exam_reminder(
                            invigilator_email=inv_email,
                            invigilator_name=exam["name"],
                            course=exam["course"],
                            date=exam["date"],
                            time=exam["time"],
                            venue=exam["venue"],
                            duration=exam["duration"], 
                            message_type="Upcoming Exam Reminder"
                        )
    
                        st.success("Near-exam reminder sent.")
    # Reported Issues
    with tab6:
    
        reported = exams[exams["issue_reported"] == True]
    
        if reported.empty:
            st.success("No issues reported")
        else:
            st.subheader("Reported Exams")
    
            for _, row in reported.iterrows():
    
                # Get current invigilator name directly (no merge)
                current_invigilator = users[
                    users["id"] == row["invigilator_id"]
                ].iloc[0]
    
                st.markdown(f"### {row['course']}")
                st.write("Current Invigilator:", current_invigilator["name"])
                st.write("Issue:", row["issue_message"])
                st.write("Venue:", row["venue"])
                st.write("Date:", row["date"])
                st.write("Time:", row["time"])
                st.write("Number of Students:", row["num_students"])
    
                st.markdown("#### Reassign Exam")
    
                invigilators = users[users["role"] == "invigilator"]
    
                new_invigilator_name = st.selectbox(
                    "Select New Invigilator",
                    invigilators["name"],
                    key=f"reassign_{row['id']}"
                )
    
                if st.button("Confirm Reassignment", key=f"btn_{row['id']}"):
    
                    new_invigilator = invigilators[
                        invigilators["name"] == new_invigilator_name
                    ].iloc[0]
    
                    exams.loc[exams["id"] == row["id"], "invigilator_id"] = new_invigilator["id"]
                    exams.loc[exams["id"] == row["id"], "issue_reported"] = False
                    exams.loc[exams["id"] == row["id"], "issue_message"] = ""
                    exams.loc[exams["id"] == row["id"], "status"] = "Pending"
    
                    save_exams(exams)

                    send_exam_notification(
                        new_invigilator["email"],
                        new_invigilator["name"],
                        row["course"],
                        row["venue"],
                        row["date"],
                        row["time"],
                        row["duration"]
                    )
    
                    st.success("Exam reassigned & new invigilator notified!")
                    st.rerun()
    
                st.divider()
