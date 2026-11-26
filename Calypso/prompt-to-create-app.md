# Prompt to Create the ShopAI Chat Application from `Portrait.md`

Place **`Portrait.md`** inside a new empty project folder, open your AI coding agent in that folder, and paste this prompt:

```text
Read Portrait.md in full and execute the complete build specification and Section 12 ("Ready-to-use prompt for the next agent") end-to-end. Start with Step 0 (ask me what shop name I want for <SHOP_NAME> before creating files), then build the entire frontend, documented FastAPI backend, commented requirements.txt and Dockerfile, README + Troubleshooting guides, high-resolution architecture diagrams (.html and .png), and offline pytest suite until 100% of tests pass.
```

---

## What Will Happen When You Run This Prompt

1. **Step 1 — Storefront Name Prompt:** The AI agent will ask: *"What name would you like to use for your shop/storefront?"*
2. **Step 2 — Automated Build & Verification:** Once you reply with your shop name, the agent will automatically build the entire project (with inline comments in `app/main.py`, `public/js/chat.js`, `public/js/app.js`, `requirements.txt`, and `Dockerfile`), render the `.png` architecture diagrams, generate `README.md` + `Troubleshooting.md` + `Architecture.md`, and run `pytest` until all tests pass.
3. **Step 3 — Run Locally with Docker:** Copy `.env.example` to `.env`, set your F5 CAI credentials, and start the container:
   ```bash
   cp .env.example .env
   # Edit .env with your F5 CAI token, CAI Project name, and AI model
   docker build -t shopai-chat .
   docker run --rm -p 80:80 --env-file .env --name shopai-chat shopai-chat
   ```
   Then open `http://localhost` in your browser.
