import re
import dns.resolver
import smtplib
import pandas as pd
import streamlit as st
import time
import random

# ---------- EMAIL LOGIC ---------- #

def is_valid_email(email):
    """
    Checks if the given email address is valid using a regular expression.
    """
    regex = r"""(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)])"""
    return re.fullmatch(regex, email) is not None


def get_resolver():
    """
    Uses public DNS servers for MX lookup.
    """
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = ["8.8.8.8", "1.1.1.1"]
    resolver.timeout = 10
    resolver.lifetime = 10
    return resolver


def _smtp_check_deliverability(email, domain, mx_records):
    """
    Attempts to perform a basic SMTP check to see if the mailbox exists,
    and detect if the domain is an 'accept all' domain.

    Returns:
        (is_deliverable, is_accept_all, smtp_message_code)
    """
    is_deliverable = False
    is_accept_all = False
    smtp_code = None

    dummy_email = f"nonexistentuser_{random.randint(10000, 99999)}@{domain}"

    for record in mx_records:
        mail_server = str(record.exchange).rstrip(".")
        try:
            server = smtplib.SMTP(timeout=10)
            server.set_debuglevel(0)
            server.connect(mail_server, 25)
            server.helo(server.local_hostname)
            server.mail("noreply@gmail.com")

            code_actual, message_actual = server.rcpt(email)
            smtp_code = code_actual

            code_dummy, message_dummy = server.rcpt(dummy_email)

            server.quit()

            if code_actual == 250:
                if code_dummy == 250:
                    print(
                        f"SMTP check for {email} on {mail_server}: "
                        f"Likely Accept All Domain. Actual email: {code_actual}, Dummy: {code_dummy}"
                    )
                    is_accept_all = True
                    is_deliverable = True
                    return is_deliverable, is_accept_all, smtp_code

                elif code_dummy == 550:
                    print(
                        f"SMTP check for {email} on {mail_server}: "
                        f"Deliverable. Actual email: {code_actual}, Dummy: {code_dummy}"
                    )
                    is_deliverable = True
                    is_accept_all = False
                    return is_deliverable, is_accept_all, smtp_code

                else:
                    try:
                        dummy_msg = message_dummy.decode()
                    except Exception:
                        dummy_msg = str(message_dummy)
                    print(
                        f"SMTP check for {email} on {mail_server}: "
                        f"Ambiguous response for dummy ({code_dummy} {dummy_msg}). "
                        f"Actual: {code_actual}. Trying next MX if available."
                    )

            elif code_actual == 550:
                try:
                    actual_msg = message_actual.decode()
                except Exception:
                    actual_msg = str(message_actual)
                print(
                    f"SMTP check for {email} on {mail_server}: "
                    f"Recipient rejected ({code_actual} {actual_msg})"
                )
                is_deliverable = False
                is_accept_all = False
                return is_deliverable, is_accept_all, smtp_code

            else:
                try:
                    actual_msg = message_actual.decode()
                except Exception:
                    actual_msg = str(message_actual)
                print(
                    f"SMTP check for {email} on {mail_server}: "
                    f"Unexpected response for actual email ({code_actual} {actual_msg}). "
                    f"Trying next MX if available."
                )

        except smtplib.SMTPConnectError as e:
            print(f"SMTP connection error to {mail_server} for {email}: {e}")
        except smtplib.SMTPServerDisconnected as e:
            print(f"SMTP server disconnected unexpectedly for {email} on {mail_server}: {e}")
        except Exception as e:
            print(f"Other SMTP error for {email} on {mail_server}: {e}")

    return is_deliverable, is_accept_all, smtp_code


def check_email_status(email):
    """
    Checks the validity, MX records, and deliverability status of an email,
    including detection of 'accept all' domains.

    Returns:
        (is_valid_format, has_mx_records, is_deliverable, is_accept_all, smtp_response_code)
    """
    is_valid_format = is_valid_email(email)
    has_mx_records = False
    is_deliverable = False
    is_accept_all = False
    smtp_response_code = None

    if not is_valid_format:
        return is_valid_format, has_mx_records, is_deliverable, is_accept_all, smtp_response_code

    domain = email.split("@")[1]
    mx_records = []
    try:
        resolver = get_resolver()
        mx_records = resolver.resolve(domain, "MX")
        has_mx_records = len(mx_records) > 0
    except dns.resolver.NXDOMAIN:
        has_mx_records = False
    except dns.resolver.NoAnswer:
        has_mx_records = False
    except Exception as e:
        print(f"Error resolving MX records for {email}: {e}")
        has_mx_records = False

    if has_mx_records:
        is_deliverable, is_accept_all, smtp_response_code = _smtp_check_deliverability(
            email, domain, mx_records
        )

    return is_valid_format, has_mx_records, is_deliverable, is_accept_all, smtp_response_code


def build_result_row(email):
    is_valid, has_mx, is_deliv, is_accept_all_domain, smtp_code = check_email_status(email)

    return {
        "Email": email,
        "Valid Format": "Yes" if is_valid else "No",
        "Has MX Records": "Yes" if has_mx else "No",
        "Deliverable": "Yes" if is_deliv else "No",
        "Accept All Domain": "Yes" if is_accept_all_domain else "No",
        "SMTP Response Code": smtp_code if smtp_code is not None else ""
    }


# ---------- UI ---------- #

st.set_page_config(page_title="Email Verifier", layout="centered")
st.title("📧 Email Verifier")

option = st.radio(
    "Choose Input Method",
    ["Single Email", "Upload CSV"]
)

results = []

if option == "Single Email":
    email = st.text_input("Enter Email")

    if st.button("Verify"):
        if email:
            with st.spinner("Checking..."):
                results.append(build_result_row(email.strip()))
        else:
            st.warning("Please enter an email")

if option == "Upload CSV":
    file = st.file_uploader("Upload CSV (column name: email)", type=["csv"])

    if file:
        df = pd.read_csv(file)

        if "email" not in df.columns:
            st.error("CSV must contain 'email' column")
        else:
            if st.button("Verify All"):
                progress_bar = st.progress(0)
                status_text = st.empty()

                email_list = [str(email).strip() for email in df["email"].dropna().tolist()]
                total_emails = len(email_list)

                for idx, email in enumerate(email_list, start=1):
                    status_text.text(f"Processing {idx} of {total_emails}: {email}")
                    results.append(build_result_row(email))

                    if idx < total_emails:
                        time.sleep(random.uniform(2, 8))

                    progress_bar.progress(idx / total_emails)

                status_text.text("Processing complete.")

if results:
    df_results = pd.DataFrame(results)
    st.dataframe(df_results, use_container_width=True)

    csv_data = df_results.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="📥 Download Results CSV",
        data=csv_data,
        file_name="email_verification_results.csv",
        mime="text/csv"
    )

    st.markdown("""
    ### Output Columns
    - **Email**
    - **Valid Format**
    - **Has MX Records**
    - **Deliverable**
    - **Accept All Domain**
    - **SMTP Response Code**
    """)
