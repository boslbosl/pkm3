# SpecStory history

_**User**_

How do I enable CORS in FastAPI?

_**Assistant**_

Add CORSMiddleware from starlette.middleware.cors and configure allow_origins.

_**User**_

Can I restrict it to one origin?

_**Assistant**_

Yes — set allow_origins=["https://example.com"].
