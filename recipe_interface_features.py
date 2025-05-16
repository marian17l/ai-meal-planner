import streamlit as st
import requests
import json
from fpdf import FPDF  # PDF generation

# Constants
API_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY = st.secrets["OPENROUTER_API_KEY"]

# Cached AI call to avoid duplicate requests
@st.cache_data(show_spinner=False)
def get_meal_suggestions(messages):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "Recipe Meal Planner"
    }
    data = {
        "model": "meta-llama/llama-4-maverick:free",
        "messages": messages,
        "max_tokens": 600
    }
    resp = requests.post(API_URL, json=data, headers=headers)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

# PDF creation of saved recipes
def create_pdf(title: str, content: str) -> bytes:
    safe_title   = title.encode("latin-1", "ignore").decode("latin-1")
    safe_content = content.encode("latin-1", "ignore").decode("latin-1")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 10, safe_title, ln=1, align="C")
    pdf.ln(4)

    for line in safe_content.splitlines():
        text = line.strip()
        if not text:
            pdf.ln(2)
            continue
        if text.startswith("# "):
            heading = text[2:].strip()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, heading, ln=1)
        elif text.startswith("## "):
            heading = text[3:].strip()
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 8, heading, ln=1)
        elif text.startswith("### "):
            heading = text[4:].strip()
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, heading, ln=1)
        else:
            pdf.set_font("Arial", "", 12)
            pdf.multi_cell(0, 6, text)

    return pdf.output(dest="S").encode("latin-1")


# Session state init
for key in ["history", "saved", "latest_recipe", "latest_prompt",
            "messages", "substitute_mode", "ingredient_to_sub"]:
    if key not in st.session_state:
        st.session_state[key] = "" if "recipe" in key or "prompt" in key else []

# UI Setup
st.set_page_config(page_title="🍽️ AI Meal Planner", layout="wide")
st.title("👩‍🍳 Welcome to your Personal Meal Planner!")
st.subheader("Use the tabs below to generate or view saved recipes.")

# Sidebar: recipe history titles
st.sidebar.title("📜 Recipe History")
if st.session_state.history:
    for i, title in enumerate(reversed(st.session_state.history)):
        st.sidebar.markdown(f"**{len(st.session_state.history) - i}.** {title}")
else:
    st.sidebar.info("No recipes yet.")

# Two tabs: Generator & Saved
tab1, tab2 = st.tabs(["Recipe Generator", "Saved Recipes"])

with tab1:
    st.subheader("Generate a New Recipe")
    with st.form("meal_form"):
        # Basic inputs
        ingredients            = st.text_input("Ingredients you have at hand (comma-separated):")
        meal_type              = st.text_input("What kind of meal are you looking for? (e.g. dinner, snack)")
        dietary_needs          = st.text_input("Do you have any dietary needs (e.g., vegan, gluten-free):")
        prep_time              = st.text_input("Maximum preparation time preference (in minutes):")
        portion_size           = st.text_input("How many portion sizes do you want to cook?")

        # Advanced options in an expander
        with st.expander("Advanced Options"):
            tools                  = st.text_input("Any cooking tools you don't have:")
            nutritional_breakdown  = st.text_input("Do you want a nutritional breakdown of the meal?")
            additional_preferences = st.text_input("Any additional preferences (e.g., low fat, high protein)?:")
        
        submitted = st.form_submit_button("Get Meal Suggestion")

    if submitted:
        user_prompt = (
            "You are a helpful and knowledgeable meal planning assistant with many years of experience in several types of cousine.\n"
            f"You will generate a tailored recipe based on the user preferences and needs stated below\n"
            f"Ingredients that user currently has: {ingredients}\n"
            f"The kind of meal the user wants to cook: {meal_type}\n"
            f"Dietary Needs: {dietary_needs}\n"
            f"Preparation Time Preference: {prep_time} minutes\n"
            f"If the user answers 'yes' for this question, they want a nutritional breakdown of the meal so also include the info in the recipe, if they answered 'no', you don't display that info: {nutritional_breakdown}\n"
            f"Portion size the user wants to cook: {portion_size}\n"
            f"Tools the user does not have available: {tools}\n"
            f"Additional Preferences of the user: {additional_preferences}\n"
            f"When listing ingredients, make sure to always use metric system i.e. grams, liters, etc. NOT imperial system.\n"
            f"You may use extra ingredients if needed, but clearly list them at the end under a section titled '🛒 Shopping List'.\n"
            f"Clearly structure your response like this, each point being a separate headline:\n"
            f"1. Recipe title (as a top-level Markdown heading, # Title)\n"
            f"2. Preparation time of the meal (## Preparation Time)\n"
            f"3. Ingredients List (including both user's and extra ones as subheading ## Ingredients)\n"
            f"4. Any special tools they need but might not have (## Tools)\n"
            f"5. Step-by-step instructions (## Instructions)\n"
            f"6. 🛒 Shopping List (only the ingredients the user didn't provide, under ## Shopping List)\n"
            f"At the end, add a friendly sign-off like 'Enjoy your meal!' or 'Bon Appétit!'."
        )

        messages = [{"role": "user", "content": user_prompt}]

        with st.spinner("🍳 Cooking up ideas..."):
            # Debug—make sure this runs
            st.write("🚧 DEBUG: about to call get_meal_suggestions()")
            response = get_meal_suggestions(messages)
            # Debug—see exactly what we got back (first 200 chars)
            st.write("🚧 DEBUG: raw response:", response[:200])

            # Store the raw recipe
            st.session_state.latest_recipe = response

            # Extract title
            title = next(
                (line.strip('# ').strip() for line in response.splitlines() if line.strip()),
                "Untitled Recipe"
            )    

            # Store context & history
            st.session_state.latest_prompt = user_prompt
            st.session_state.messages = [
                {"role": "user",      "content": user_prompt},
                {"role": "assistant", "content": response}
            ]
            st.session_state.history.append(title)


    # Display the generated recipe
    if st.session_state.latest_recipe:
        st.markdown("### 🍽️ Your Meal Suggestion")
        st.write(st.session_state.latest_recipe)

        # Substitution block
        with st.expander("🔁 Ingredient Substitution"):
            st.session_state.substitute_mode = st.checkbox("I want to substitute an ingredient")
            if st.session_state.substitute_mode:
                st.session_state.ingredient_to_sub = st.text_input("Which ingredient would you like to substitute?")
                if st.button("Suggest Alternatives") and st.session_state.ingredient_to_sub:
                    st.session_state.messages.append({
                        "role": "user",
                        "content": f"I would like to substitute '{st.session_state.ingredient_to_sub}'. "
                                   "Can you suggest 2–3 alternatives and explain why?"
                    })
                    try:
                        sub_resp = get_meal_suggestions(st.session_state.messages)
                        st.session_state.messages.append({"role": "assistant", "content": sub_resp})
                        st.markdown(f"### 🔄 Substitution for '{st.session_state.ingredient_to_sub}'")
                        st.write(sub_resp)
                    except Exception as e:
                        st.error(f"Error during substitution: {e}")

        # Save button
        if st.button("💾 Save this recipe"):
            st.session_state.saved.append({
                "title": title,
                "content": st.session_state.latest_recipe
            })
            st.success("Recipe saved to your library!")

        # Regenerate button
        if st.button("🔄 Regenerate Recipe"):
            st.session_state.messages.append({
                "role": "user",
                "content": "I didn't like the previous recipe. Please generate a new one."
            })
            with st.spinner("🌀 Generating a new recipe..."):
                try:
                    new_resp = get_meal_suggestions(st.session_state.messages)
                    st.session_state.messages.append({"role": "assistant", "content": new_resp})
                    st.session_state.latest_recipe = new_resp
                    # extract & save new title
                    new_title = next(
                        (ln.strip('# ').strip() for ln in new_resp.splitlines() if ln.strip()),
                        "Untitled Recipe"
                    )
                    st.session_state.history.append(new_title)
                except Exception as e:
                    st.error(f"Error regenerating recipe: {e}")

with tab2:
    st.subheader("📚 Your Saved Recipes")
    if not st.session_state.saved:
        st.info("You haven't saved any recipes yet.")
    else:
        for idx, rec in enumerate(st.session_state.saved, 1):
            st.markdown(f"#### {idx}. {rec['title']}")
            st.write(rec["content"])
            pdf_bytes = create_pdf(rec["title"], rec["content"])
            st.download_button(
                label="📄 Download as PDF",
                data=pdf_bytes,
                file_name=f"{rec['title']}.pdf",
                mime="application/pdf",
                key=f"pdf_{idx}"
            )
