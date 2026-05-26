from fastapi import FastAPI
from VoiceVerbatimAPI import create_fastapi_app, NotesRouter

def main():
  app = create_fastapi_app()
  notes_apis = NotesRouter()
  app.include_router(notes_apis.router)


if __name__ == "__main__":
  main()