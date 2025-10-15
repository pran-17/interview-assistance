# === Install dependencies first ===
# pip install streamlit speechrecognition pyaudio textblob transformers torch PyPDF2

import streamlit as st
import speech_recognition as sr
from textblob import TextBlob
from transformers import pipeline
import PyPDF2
import torch
import random
import time 
import hashlib

# === Initialize Models ===
@st.cache_resource
def load_models():
    """Load heavy models once and cache them."""
    sentiment_model = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
    question_generator = pipeline("text-generation", model="distilgpt2", max_new_tokens=60, pad_token_id=50256)
    recognizer = sr.Recognizer()
    return sentiment_model, question_generator, recognizer

sentiment_model, question_generator, recognizer = load_models()

# === Helper: Extract Text from Resume ===
def extract_text_from_pdf(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text

# === Helper: Simple NLP to extract resume insights ===
def extract_resume_insights(resume_text):
    """Extract lightweight insights (skills, projects, domains) from resume using NLP heuristics."""
    safe_text = str(resume_text or "")
    blob = TextBlob(safe_text)
    noun_phrases = [np.lower() for np in blob.noun_phrases if 2 <= len(np) <= 60]

    # Basic skill keyword list (extendable)
    canonical_skills = [
        "python", "java", "c++", "javascript", "node", "react", "angular", "django", "flask",
        "sql", "mysql", "postgres", "mongodb", "git", "docker", "kubernetes", "aws", "azure",
        "gcp", "ml", "machine learning", "deep learning", "nlp", "data science", "pandas",
        "numpy", "scikit-learn", "pytorch", "tensorflow", "devops", "microservices"
    ]

    text_lc = safe_text.lower()
    detected_skills = sorted({s for s in canonical_skills if s in text_lc})

    # Heuristic project extraction: lines or phrases containing 'project' or 'developed/built'
    possible_projects = []
    for line in safe_text.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue
        l = line_stripped.lower()
        if "project" in l or "developed" in l or "built" in l or "implemented" in l:
            possible_projects.append(line_stripped)

    # Domains from noun phrases
    domain_candidates = [p for p in noun_phrases if any(k in p for k in ["system", "platform", "pipeline", "application", "model", "api", "service", "dashboard", "analysis"])]

    return {
        "noun_phrases": noun_phrases[:100],
        "skills": detected_skills[:30],
        "projects": possible_projects[:10],
        "domains": domain_candidates[:20],
    }

# === Helper: Question categories rotation ===
def get_question_categories():
    return [
        "projects",            # deep dive into a specific project
        "technical_skills",    # skills-focused question
        "experience",          # role/impact/responsibility
        "achievements",        # measurable outcomes
        "education",           # coursework/research/certifications
        "behavioral"           # soft-skill/behavioral related to resume contexts
    ]

# === Helper: Generate AI Interview Question ===
def generate_ai_interview_question(resume_text, category=None, previous_answer=None, previous_question=None, insights=None):
    """
    Generate an interview question based on the resume and desired category.
    Optionally consider the previous answer to follow up more intelligently.
    """
    if insights is None:
        insights = extract_resume_insights(resume_text)

    prompt_context = resume_text[:900]
    skills = ", ".join(insights.get("skills", [])[:8]) or "relevant technical skills"
    sample_project = insights.get("projects", [""])[:1]
    project_hint = sample_project[0] if sample_project else "one of the projects mentioned"
    domains_hint = ", ".join(insights.get("domains", [])[:5]) or "key domains"

    category = category or "general"
    follow_up = (previous_answer or "").strip()
    prev_q = (previous_question or "").strip()

    instruction_by_category = {
        "projects": f"Ask a specific question that dives into the candidate's project work, preferably about '{project_hint}'. Focus on challenges, decisions, and results.",
        "technical_skills": f"Ask a question to assess depth in these skills: {skills}. Require concrete examples.",
        "experience": "Ask about responsibilities, scope, and impact in a recent role.",
        "achievements": "Ask for measurable outcomes, metrics, or before-after improvements.",
        "education": "Ask about relevant coursework, research, or certifications tied to the role.",
        "behavioral": f"Ask a behavioral question tied to situations likely from their resume domains: {domains_hint}.",
        "general": "Ask a professional, resume-grounded question that an interviewer might ask."
    }

    follow_up_clause = (
        f" Also, make it a natural follow-up to this answer: '{follow_up}'." if len(follow_up.split()) > 5 else ""
    )
    anti_repeat_clause = (
        f" Do NOT repeat or paraphrase this previous question: '{prev_q}'. Ask a different aspect." if len(prev_q.split()) > 3 else ""
    )

    unique_id = time.time_ns()
    prompt = (
        f"You are an expert interviewer. Using the resume snippet and instruction, craft ONE clear question."
        f"\nInstruction: {instruction_by_category.get(category, instruction_by_category['general'])}{follow_up_clause}{anti_repeat_clause}"
        f"\nResume Snippet (keep private, don't repeat it verbatim):\n{prompt_context}"
        f"\nUnique ID: {unique_id}\nQuestion:"
    )

    try:
        ai_output = question_generator(
            prompt,
            num_return_sequences=1,
            do_sample=True,
            temperature=0.9,
            top_k=50,
            max_new_tokens=60
        )[0]['generated_text']

        question = ai_output.split("Question:")[-1].strip()
        question = question.split("Unique ID:")[0].strip()

        if len(question.split()) < 5 or not question.endswith('?'):
            # Templated fallbacks by category
            fallback_by_category = {
                "projects": f"Can you walk me through {project_hint} from your resume, highlighting a tough technical decision and its impact?",
                "technical_skills": f"Which of these skills ({skills}) have you applied most recently, and how did you use it?",
                "experience": "What were your primary responsibilities in your most recent role and how did you measure success?",
                "achievements": "What accomplishment from your resume are you most proud of and why?",
                "education": "Which coursework or certification best prepared you for this role and how?",
                "behavioral": "Describe a time you handled a tight deadline or conflicting priorities. What did you do?",
                "general": "Tell me about a project from your resume that best showcases your strengths."
            }
            question = fallback_by_category.get(category, fallback_by_category["general"])

        return question[0].upper() + question[1:]

    except Exception as e:
        st.error(f"⚠️ AI Question Generation Error: {str(e)}")
        return "Can you tell me about your most significant professional achievement as listed in your resume?"

# === Helper: Analyze Answer ===
def analyze_text(text):
    """Analyze candidate's answer and return feedback dict."""
    feedback = {}

    # Sentiment
    sentiment = sentiment_model(text)[0]
    feedback['Sentiment'] = f"{sentiment['label']} (Score: {sentiment['score']:.2f})"

    # Grammar
    corrected_text = str(TextBlob(text).correct())
    if corrected_text != text:
        feedback['Grammar'] = f"Suggested correction: {corrected_text}"
    else:
        feedback['Grammar'] = "Looks good ✅"

    # Filler words
    fillers = ["um", "uh", "like", "you know", "actually", "so", "and stuff"]
    found_fillers = [w for w in fillers if w in text.lower().split()]
    feedback['Filler Words'] = "None ✅" if not found_fillers else f"Found: {', '.join(found_fillers)}"

    # Scoring (simple heuristic)
    score = 0
    if sentiment['label'] == "POSITIVE":
        score += 30
    if not found_fillers:
        score += 20
    if corrected_text == text:
        score += 30
        
    # Content length heuristic (encourage detailed answers)
    if len(text.split()) > 30:
        score += 20
    
    # Cap score at 100
    final_score = min(score, 100)
    feedback['Candidate Score'] = f"{final_score}/100"

    return feedback

# === Helper: Record & Transcribe Speech (actual mic recording) ===
def transcribe_speech(lang_code="en-IN", duration=10):
    """Record from default microphone and transcribe using Google Web Speech API."""
    try:
        with sr.Microphone() as source:
            # Reduce ambient noise and capture
            recognizer.adjust_for_ambient_noise(source, duration=0.8)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=duration)
        # Perform recognition
        text = recognizer.recognize_google(audio, language=lang_code)
        return text
    except sr.WaitTimeoutError:
        return ""
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        st.error(f"Speech API error: {e}")
        return ""

# === NEW HELPER: Generate Next Question and Clear State (MODIFIED) ===
def generate_next_question(resume_text):
    """Generate the next question based on rotating categories and previous answer."""
    if not isinstance(resume_text, str) or not resume_text.strip():
        st.error("Cannot generate a new question: Resume text is missing.")
        return

    if "resume_insights" not in st.session_state:
        st.session_state["resume_insights"] = extract_resume_insights(resume_text)

    if "question_categories" not in st.session_state:
        st.session_state["question_categories"] = get_question_categories()
    if "category_index" not in st.session_state:
        st.session_state["category_index"] = 0

    categories = st.session_state["question_categories"]
    idx = st.session_state["category_index"]
    category = categories[idx % len(categories)] if categories else "general"

    # Prefer the most recent non-empty answer
    prev_answer = ""
    ta = str(st.session_state.get("typed_answer", "") or "").strip()
    tr = str(st.session_state.get("transcribed_text", "") or "").strip()
    if tr:
        prev_answer = tr
    elif ta:
        prev_answer = ta

    with st.spinner("Generating next interview question..."):
        last_q = str(st.session_state.get("current_question", "") or "")
        tried = 0
        next_question = ""
        # Try up to len(categories) times rotating category to avoid repetition
        while tried < max(1, len(categories)):
            next_question = generate_ai_interview_question(
                resume_text,
                category=category,
                previous_answer=prev_answer,
                previous_question=last_q,
                insights=st.session_state["resume_insights"],
            )
            if next_question and next_question.strip() and next_question.strip() != last_q.strip():
                break
            # rotate to next category
            idx = (idx + 1) % max(1, len(categories))
            category = categories[idx]
            tried += 1

        st.session_state["current_question"] = next_question

        # Clear answer fields for the next question
        st.session_state["transcribed_text"] = ""
        st.session_state["typed_answer"] = ""

    # Advance category index for next time
    st.session_state["category_index"] = (idx + 1) % max(1, len(categories))
    st.rerun()


# === Streamlit App ===
st.title("🤖 AI-Powered Interview Assistant (Dynamic Question Generator)")
st.write("Upload your **resume**, get **AI-generated interview questions**, and receive **real-time feedback** on your answers (speech + text).")

# === Resume Upload ===
uploaded_resume = st.file_uploader("📄 Upload Resume (PDF)", type=["pdf"])
resume_text = ""

if uploaded_resume is not None:
    try:
        resume_text = extract_text_from_pdf(uploaded_resume)
        if resume_text.strip():
            st.success("✅ Resume uploaded and processed successfully!")
            st.write(f"**Extracted {len(resume_text.split())} words from resume.**")
            # Cache insights and reset category rotation ONLY when the resume changes
            new_hash = hashlib.md5(resume_text.encode("utf-8")).hexdigest()
            prev_hash = st.session_state.get("resume_hash")
            if new_hash != prev_hash:
                st.session_state["resume_hash"] = new_hash
                st.session_state["resume_insights"] = extract_resume_insights(resume_text)
                st.session_state["question_categories"] = get_question_categories()
                st.session_state["category_index"] = 0
        else:
            st.warning("⚠️ Could not extract text from the PDF. The file might be image-based or protected.")
    except Exception as e:
        st.error(f"An error occurred while processing the PDF: {e}")
        resume_text = ""

# Maintain session state
if "current_question" not in st.session_state:
    st.session_state["current_question"] = None
if "typed_answer" not in st.session_state:
    st.session_state["typed_answer"] = ""


# === Generate Initial AI Question Button ===
if uploaded_resume is not None and isinstance(resume_text, str) and resume_text.strip():
    # Only show the button to start the interview or if the user wants to skip the current question
    if st.button("🎯 Generate Question"):
        generate_next_question(resume_text)
else:
    st.info("Upload a resume (PDF with selectable text) to enable AI question generation.")
    st.session_state["current_question"] = None


# === Display AI-Generated Question and Answer Logic ===
if st.session_state["current_question"]:
    st.markdown("---")
    st.markdown(f"### 🧠 AI-Generated Question (Based on your Resume):")
    st.info(st.session_state["current_question"])

    # === Language Selection ===
    languages = {
        "English (India)": "en-IN",
        "English (US)": "en-US",
        "Hindi": "hi-IN",
        "Tamil": "ta-IN",
        "Telugu": "te-IN"
    }
    lang_code = st.selectbox("🎙️ Select Input Language:", list(languages.keys()))
    code = languages[lang_code]

    # === Answer Input Options ===
    st.write("You can either **speak** your answer or **type** it below:")

    if "transcribed_text" not in st.session_state:
        st.session_state["transcribed_text"] = ""
        
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### Speak Answer")
        if st.button("🎤 Start Speaking"):
            with st.spinner(f"Recording and transcribing ({lang_code})..."):
                transcribed_text_result = transcribe_speech(lang_code=code)
                st.session_state["transcribed_text"] = transcribed_text_result
            st.rerun()

        # 4. Display result and analysis
        if st.session_state["transcribed_text"]:
            st.text_area("📝 Transcribed Answer:", st.session_state["transcribed_text"], height=120, key="transcribed_text_area_display")
            
            if st.session_state["transcribed_text"].strip():
                feedback = analyze_text(st.session_state["transcribed_text"])
                st.subheader("📊 Feedback & Evaluation")
                for key, val in feedback.items():
                    st.write(f"**{key}:** {val}")
                
                # Feedback is shown; click 'Next Question' below to proceed
            else:
                st.warning("Could not transcribe speech. Please try again or type your answer.")

    with col2:
        st.write("### Type Answer")
        manual_text = st.text_area("✍️ Type Your Answer Here:", value=st.session_state.get("typed_answer", ""), key="manual_text_area")
        
        st.session_state["typed_answer"] = manual_text
        
        if st.button("🔍 Analyze Typed Answer"):
            if manual_text.strip():
                feedback = analyze_text(manual_text)
                st.subheader("📊 Feedback & Evaluation")
                for key, val in feedback.items():
                    st.write(f"**{key}:** {val}")
                # Feedback is shown; click 'Next Question' below to proceed
            else:
                st.warning("Please enter an answer to analyze.")

    st.markdown("\n")
    # Next Question control – will use resume, rotate category, and consider the last answer if present
    if st.button("⏭️ Next Question"):
        generate_next_question(resume_text)