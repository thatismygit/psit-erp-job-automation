import requests
from bs4 import BeautifulSoup
from datetime import datetime
from tabulate import tabulate
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv
import pytz

load_dotenv()

login_url = os.getenv("LOGIN_URL")

credentials = {
    "username": os.getenv("ERP_USERNAME"),
    "password": os.getenv("ERP_PASSWORD")
}


SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

session = requests.Session()
session.post(login_url, data=credentials)

job_inbox_url = os.getenv("JOB_INBOX_URL")
response = session.get(job_inbox_url)

soup = BeautifulSoup(response.text, "html.parser")

# Indian Time
ist = pytz.timezone("Asia/Kolkata")
current_time = datetime.now(ist)

jobs = soup.find_all("div", class_="row g-0")[:5]

results = []

for job in jobs:

    company_name = job.find("td", string="Company Name")
    if company_name:
        company_name = company_name.find_next("td").text.strip()
    else:
        company_name = "Unknown Company"

    # Extract Last Date
    last_date_tag = job.find("td", string="Last Date to Apply")
    expired = False
    last_date_text = ""

    if last_date_tag:
        last_date_text = last_date_tag.find_next("td").text.strip()
        try:
            last_date = datetime.strptime(last_date_text, "%d %b %Y [%H:%M]")
            last_date = ist.localize(last_date)
            if current_time > last_date:
                expired = True
        except:
            pass

    # Check applied image
    applied_img = job.find("img", src=lambda x: x and "applied_successfully.png" in x)

    if applied_img:
        applied_date = applied_img.get("title", "Already Applied")
        results.append([company_name, "Already Applied", applied_date])
        continue

    if expired:
        results.append([company_name, "Expired", last_date_text])
        continue

    # Extract job link
    link_tag = job.find("a", href=True)
    if not link_tag:
        continue

    link = link_tag["href"]
    job_id = link.strip("/").split("/")[-2]

        # ---------------------------------------
    # OPEN JOB DESCRIPTION PAGE
    # ---------------------------------------
    job_page = session.get(link)
    job_soup = BeautifulSoup(job_page.text, "html.parser")

    # Get panel-body
    panel_body = job_soup.find("div", class_="panel-body")

    if panel_body:

        # Remove all forms (modals, inputs, apply buttons)
        for form in panel_body.find_all("form"):
            form.decompose()

        # Remove Interested / Not Interested section
        interested_section = panel_body.find(string=lambda x: x and "Interested" in x)
        if interested_section:
            parent = interested_section.find_parent("table")
            if parent:
                parent.decompose()

        # Convert to HTML
        full_html_content = str(panel_body)

    else:
        full_html_content = "<p>No content found</p>"

    
    # Logo
    logo_tag = job_soup.find("img")
    logo_url = logo_tag["src"] if logo_tag else ""

    # Job Description
    jd_section = job_soup.find("h3", string=lambda x: x and "Job Description" in x)
    job_description = jd_section.find_next("table").text.strip() if jd_section else "N/A"

    # Selection Criteria
    criteria_section = job_soup.find("h3", string=lambda x: x and "Selection Criteria" in x)
    selection_criteria = criteria_section.find_next("table").text.strip() if criteria_section else "N/A"

    # Selection Process
    process_section = job_soup.find("h3", string=lambda x: x and "Selection Process" in x)
    selection_process = process_section.find_next("table").text.strip() if process_section else "N/A"

    # Degree
    degree_section = job_soup.find("h3", string=lambda x: x and "Degree" in x)
    degree = degree_section.find_next("table").text.strip() if degree_section else "N/A"

    # SPOC
    spoc_section = job_soup.find("h3", string=lambda x: x and "SPOC" in x)
    spoc = spoc_section.find_next("table").text.strip() if spoc_section else "N/A"

    # ---------------------------------------
    # APPLY
    # ---------------------------------------
    interested_url = f"https://erp.psit.ac.in/CR/Student_job_inbox_update/1/{job_id}"
    session.get(interested_url)

    # ---------------------------------------
    # BUILD EMAIL CONTENT
    # ---------------------------------------
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    </head>
    <body style="font-family: Arial; background:#f5f5f5; padding:20px;">

    <div style="max-width:900px; margin:auto; background:white; padding:25px; border-radius:8px;">

    <h2 style="text-align:center;">{company_name}</h2>

    {full_html_content}

    <hr>
    <p style="font-size:12px; color:gray; text-align:center;">
    Automated ERP Job Notification
    </p>

    </div>

    </body>
    </html>
    """




    # ---------------------------------------
    # SEND EMAIL
    # ---------------------------------------
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"New Job Applied: {company_name}"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = os.getenv("SENDER_EMAIL_ADDRESS")

    part = MIMEText(html_content, "html")
    msg.attach(part)

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, msg["To"], msg.as_string())
        server.quit()

        print(f"📧 Email sent for {company_name}")

    except Exception as e:
        print("Email sending failed:", e)


# Print Table
print("\n")
print(tabulate(results, headers=["Company", "Status", "Details"], tablefmt="fancy_grid"))
