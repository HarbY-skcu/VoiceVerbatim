import pytest
from fastapi import FastAPI
import VoiceVerbatimAPI as VVA

def test_create_app():
  assert isinstance(VVA.create_fastapi_app(), FastAPI)

test_create_app()