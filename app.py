import re
import dns.resolver
import smtplib
import pandas as pd
import streamlit as st

# ---------- EMAIL LOGIC ---------- #

def is_valid_email(email):
    regex = r"""(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])"""
    return re.fullmatch(regex, email) is not None


def get_resolver():
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = ["8.8.8.8", "1.1.1.1"]
    resolver.timeout = 10
    resolver.lifetime = 10
    return resolver


def smtp_check(email, mx_records):
    for record in mx_records:
        try:
            host = str(record.exchange).rstrip(".")
            server = smtplib.SMTP(host, 25, timeout=15)
            server.ehlo()
            server.mail("test@gmail.com")
            code, _ = server.rcpt(email)
            server.quit()

            if code == 250:
                return "Yes"
            elif code == 550:
                return "No"

        except:
            continue

    return "Unknown"


def check_email(email):
    is_valid = is_valid_email(email)

    if not is_valid:
        return {
            "Email": email,
            "Valid Format": "❌",
            "Has MX Records": "❌",
            "Deliverable": "❌"
        }

    def check_email(email):
    is_valid = is_valid_email(email)

    if not is_valid:
        return {
            "Email": email,
            "Valid Format": "No",
            "Has MX Records": "No",
            "Deliverable": "No"
        }

    domain = email.split("@")[1]

    try:
        resolver = get_resolver()
        mx_records = resolver.resolve(domain, "MX")
        has_mx = len(mx_records) > 0
    except:
        has_mx = False
        mx_records = []

    if has_mx:
        deliverable = smtp_check(email, mx_records)
    else:
        deliverable = "No"

    return {
        "Email": email,
        "Valid Format": "Yes",
        "Has MX Records": "Yes" if has_mx else "No",
        "Deliverable": deliverable
    }


# ---------- UI ---------- #

st.set_page_config(page_title="Email Verifier", layout="centered")
st.title("📧 Email Verifier")

option = st.radio(
    "Choose Input Method",
    ["Single Email", "Upload CSV"]
)

results = []

# ---------- SINGLE EMAIL ---------- #

if option == "Single Email":
    email = st.text_input("Enter Email")

    if st.button("Verify"):
        if email:
            with st.spinner("Checking..."):
                result = check_email(email)
                results.append(result)

        else:
            st.warning("Please enter an email")

# ---------- CSV UPLOAD ---------- #

if option == "Upload CSV":
    file = st.file_uploader("Upload CSV (column name: email)", type=["csv"])

    if file:
        df = pd.read_csv(file)

        if "email" not in df.columns:
            st.error("CSV must contain 'email' column")
        else:
            if st.button("Verify All"):
                with st.spinner("Processing bulk emails..."):
                    for email in df["email"]:
                        results.append(check_email(str(email)))

# ---------- SHOW RESULTS ---------- #

if results:
    df_results = pd.DataFrame(results)

    # Create display copy with emojis
    df_display = df_results.copy()

    def format_status(val):
        return {
            "Yes": "✅ Yes",
            "No": "❌ No",
            "Unknown": "⚠️ Unknown"
        }.get(val, val)

    for col in ["Valid Format", "Has MX Records", "Deliverable"]:
        df_display[col] = df_display[col].apply(format_status)

    st.dataframe(df_display)

    # ---------- DOWNLOAD BUTTON ---------- #
    csv = df_results.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="📥 Download Results CSV",
        data=csv,
        file_name="email_verification_results.csv",
        mime="text/csv"
    )

    st.markdown("""
    ### Legend
    - ✅ Valid / Confirmed
    - ❌ Invalid / Not Found
    - ⚠️ Could not verify (timeout / blocked)
    """)
