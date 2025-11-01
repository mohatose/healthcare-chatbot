from flask import Flask, request, jsonify, render_template
import json, pathlib, re, difflib
from flask_cors import CORS
from transformers import pipeline
from deep_translator import GoogleTranslator
import os

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Get port from environment variable or default to 5000
port = int(os.environ.get('PORT', 5000))

# -------------------------------------------------------
# 1️⃣ Load Knowledge Base, Glossary, Medicines
# -------------------------------------------------------
BASE = pathlib.Path(__file__).parent
with open(BASE / 'kb.json', encoding='utf8') as f:
    KB = json.load(f)
with open(BASE / 'glossary.json', encoding='utf8') as f:
    GLOSSARY = json.load(f)
with open(BASE / 'medicines.json', encoding='utf8') as f:
    MEDICINES = json.load(f)

# -------------------------------------------------------
# 2️⃣ Enhanced QA Model (with error handling for deployment)
# -------------------------------------------------------
print("🔍 Loading QA model...")
qa_model = None
try:
    qa_model = pipeline("question-answering", model="deepset/bert-base-cased-squad2")
    print("✅ QA model loaded successfully")
except Exception as e:
    print(f"❌ QA model failed to load: {e}")
    print("⚠️  Continuing without QA model - using knowledge base only")

# -------------------------------------------------------
# 3️⃣ Enhanced Vocabulary with Priority Matching
# -------------------------------------------------------

# Special high-priority patterns for common medication queries
SPECIAL_MEDICATION_PATTERNS = {
    'arv_examples': {
        'patterns': ['examples of arv', 'arv examples', 'list of arv', 'arv drugs', 'hiv drugs list', 
                    'arv medications', 'types of arv', 'arv list', 'hiv medications', 'give me examples of arv'],
        'medicine_key': 'arv_examples',
        'priority': 10
    },
    'arv_definition': {
        'patterns': ['what is arv', 'arv keng', 'arv meaning', 'define arv', 'arv ke eng', 'art keng', 'art ke eng'],
        'glossary_key': 'art',
        'priority': 9
    },
    'hiv_definition': {
        'patterns': ['what is hiv', 'hiv keng', 'hiv meaning', 'define hiv', 'hiv ke eng'],
        'glossary_key': 'hiv', 
        'priority': 9
    }
}

# Build comprehensive vocabulary
VOCAB = {}

# Add KB entries
for key, item in KB.items():
    for tag in item.get('tags', []):
        VOCAB[tag.lower()] = ('kb', key, 1.0)

# Add glossary entries  
for term in GLOSSARY.keys():
    VOCAB[term.lower()] = ('glossary', term, 1.0)

# Add medicine entries with higher priority
for med in MEDICINES.keys():
    VOCAB[med.lower()] = ('medicine', med, 1.2)

# Add common medication terms
medication_terms = ['arv', 'art', 'hiv drug', 'antiretroviral', 'medication', 'medicine', 'drug', 'pill', 'tablet']
for term in medication_terms:
    if term not in VOCAB:
        VOCAB[term] = ('medicine', 'arv_examples', 0.8)

# -------------------------------------------------------
# 4️⃣ Advanced Matching Functions
# -------------------------------------------------------
def normalize(text):
    text = text or ''
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]+", ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def detect_special_medication_patterns(text):
    """Detect special medication patterns with high priority"""
    clean = normalize(text)
    
    for pattern_name, pattern_info in SPECIAL_MEDICATION_PATTERNS.items():
        for pattern in pattern_info['patterns']:
            if pattern in clean:
                if 'medicine_key' in pattern_info:
                    return ('medicine', pattern_info['medicine_key'], pattern, pattern_info['priority'])
                elif 'glossary_key' in pattern_info:
                    return ('glossary', pattern_info['glossary_key'], pattern, pattern_info['priority'])
    return None

def advanced_topic_matching(user_text):
    """Advanced matching with special pattern detection"""
    if not user_text or not user_text.strip():
        return (None, None, None, 'general')
    
    clean = normalize(user_text)
    
    # FIRST: Check for special medication patterns (HIGHEST PRIORITY)
    special_match = detect_special_medication_patterns(user_text)
    if special_match:
        typ, key, matched, priority = special_match
        return (typ, key, matched, 'examples' if 'examples' in matched else 'definition')
    
    # SECOND: Exact matches in VOCAB
    for vocab_term, (typ, key, weight) in VOCAB.items():
        if vocab_term == clean:
            return (typ, key, vocab_term, 'general')
    
    # THIRD: Query contains vocabulary term
    for vocab_term, (typ, key, weight) in VOCAB.items():
        if len(vocab_term) > 2 and vocab_term in clean:
            return (typ, key, vocab_term, 'general')
    
    # FOURTH: Handle medication-specific queries
    if any(word in clean for word in ['arv', 'art', 'hiv drug', 'antiretroviral']):
        if any(word in clean for word in ['example', 'list', 'type', 'name']):
            return ('medicine', 'arv_examples', 'arv examples', 'examples')
        else:
            return ('glossary', 'art', 'art', 'definition')
    
    # FIFTH: Word-by-word matching
    best_match = None
    best_score = 0
    query_words = set(clean.split())
    
    for vocab_term, (typ, key, weight) in VOCAB.items():
        vocab_words = set(vocab_term.split())
        common_words = query_words & vocab_words
        
        if common_words:
            score = (len(common_words) / max(len(query_words), 1)) * weight
            if score > best_score:
                best_score = score
                best_match = (typ, key, vocab_term)
    
    if best_score > 0.3:
        return (*best_match, 'general')
    
    # SIXTH: Fuzzy matching
    all_terms = list(VOCAB.keys())
    matches = difflib.get_close_matches(clean, all_terms, n=1, cutoff=0.4)
    if matches:
        typ, key, weight = VOCAB[matches[0]]
        return (typ, key, matches[0], 'general')
    
    return (None, None, None, 'general')

# -------------------------------------------------------
# 5️⃣ Enhanced Response Generation
# -------------------------------------------------------
def generate_targeted_response(key, question_type, lang='en'):
    """Generate responses based on question type"""
    
    # Check KB first
    if key in KB:
        base_content = KB[key].get(lang) or KB[key].get('en')
        if base_content:
            return base_content
    
    # Check medicines
    if key in MEDICINES:
        content = MEDICINES[key].get(lang) or MEDICINES[key].get('en')
        if content:
            return content
    
    # Check glossary
    if key in GLOSSARY:
        content = GLOSSARY[key].get(lang) or GLOSSARY[key].get('en')
        if content:
            return content
    
    return None

# -------------------------------------------------------
# 6️⃣ Smart QA Fallback
# -------------------------------------------------------
def smart_qa_fallback(question, lang='en'):
    """Smarter QA fallback"""
    if not qa_model:
        return None
        
    question_en = translate_to_english(question) if lang == 'st' else question
    
    # Build context from all knowledge sources
    context_parts = []
    for key, item in KB.items():
        context_parts.append(item.get('en', ''))
    for term, info in GLOSSARY.items():
        context_parts.append(info.get('en', ''))
    for med, info in MEDICINES.items():
        context_parts.append(info.get('en', ''))
    
    context = " ".join(context_parts)
    
    try:
        result = qa_model(
            question=question_en, 
            context=context,
            max_answer_len=100,
            max_seq_len=512
        )
        
        answer = result.get('answer', '').strip()
        score = result.get('score', 0)
        
        if answer and score > 0.1 and len(answer.split()) >= 2:
            if lang == 'st':
                answer = translate_to_sesotho(answer)
            return answer
        return None
        
    except Exception:
        return None

# -------------------------------------------------------
# 7️⃣ Translation Helpers
# -------------------------------------------------------
def is_sesotho(text):
    sesotho_words = {"ke", "ha", "hona", "lefu", "joang", "tse", "tsa", "mali", "ea", "eng", "ho", "le", "ka", "lumela", "ntate", "me", "ena", "keng"}
    words = set(normalize(text).split())
    overlap = len(words & sesotho_words)
    return overlap >= 1

def translate_to_english(text):
    try:
        if len(text.strip()) > 3:
            return GoogleTranslator(source='st', target='en').translate(text)
        return text
    except:
        return text

def translate_to_sesotho(text):
    try:
        if len(text.strip()) > 3:
            return GoogleTranslator(source='en', target='st').translate(text)
        return text
    except:
        return text

# -------------------------------------------------------
# 8️⃣ Routes
# -------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    text = data.get('message', '')
    lang = data.get('lang', 'en')
    lang = lang if lang in ('en', 'st') else 'en'

    if not isinstance(text, str) or len(text.strip()) == 0:
        return jsonify({"response": "⚠️ Please type a question."})

    text = text.strip()
    print(f"📨 Received: '{text}' in {lang}")

    # Detect language
    if lang == 'en' and is_sesotho(text):
        lang = 'st'
        print(f"🔍 Detected Sesotho, switching to: {lang}")

    # Advanced topic matching
    typ, key, matched, question_type = advanced_topic_matching(text)
    print(f"🔍 Matching: type={typ}, key={key}, matched='{matched}', question_type={question_type}")
    
    reply = None

    # Generate response based on match type
    if typ and key:
        if typ == 'kb':
            reply = generate_targeted_response(key, question_type, lang)
            print(f"📚 Using KB: {key}")
        elif typ == 'glossary':
            reply = generate_targeted_response(key, question_type, lang)
            print(f"📖 Using glossary: {key}")
        elif typ == 'medicine':
            reply = generate_targeted_response(key, question_type, lang)
            print(f"💊 Using medicine: {key}")

    # Smart QA fallback
    if not reply and qa_model:
        print("🤖 Trying smart QA fallback...")
        reply = smart_qa_fallback(text, lang)
    
    # Final fallback - try to find any related content
    if not reply:
        clean_text = normalize(text)
        # Check for ARV/HIV related queries
        if any(word in clean_text for word in ['arv', 'art', 'hiv drug', 'antiretroviral']):
            if any(word in clean_text for word in ['example', 'list', 'type']):
                reply = generate_targeted_response('arv_examples', 'examples', lang)
            else:
                reply = generate_targeted_response('art', 'definition', lang)
    
    # Ultimate fallback
    if not reply:
        fallback_responses = {
            'en': "I understand you're asking about health. Could you please rephrase your question or ask about:\n• HIV treatment and ARVs\n• Maternal or child health\n• Nutrition or hygiene\n• Specific medications\n• Disease symptoms or prevention",
            'st': "Ke utloisisa hore u botsa ka bophelo. Ka kopo, buisa potso kapa u botsise ka:\n• Kalafo ea HIV le li-ARV\n• Bophelo ba bokhachane kapa bana\n• Phepo kapa bohloeki\n• Meriana e itseng\n• Matšoao a malwetse kapa thibelo"
        }
        reply = fallback_responses[lang]

    # Add disclaimer
    disclaimer = {
        'en': "\n\nNote: This is health information, not medical advice. Consult a healthcare professional.",
        'st': "\n\nTlhokomeliso: Tsena ke tlhahisoleseding ya bophelo, eseng keletso ea bongaka. Buisana le setsebi sa bophelo."
    }

    final_response = f"{reply}{disclaimer[lang]}"
    print(f"📤 Response ready")
    
    return jsonify({"response": final_response})

if __name__ == '__main__':
    print("🚀 Starting Healthcare Chatbot...")
    print("📊 Knowledge base entries:", len(KB))
    print("📖 Glossary terms:", len(GLOSSARY))
    print("💊 Medicines:", len(MEDICINES))
    
    # Use 0.0.0.0 for external access
    app.run(host='0.0.0.0', port=port, debug=False)