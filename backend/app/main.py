from fastapi import FastAPI


app = FastAPI(
    title="Business Dashboard API",
    version="0.1.0",
    description="企业 AI 经营驾驶舱 MVP API",
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
