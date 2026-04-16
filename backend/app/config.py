from pydantic_settings import BaseSettings
 
class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
 
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
 
    # Email
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_PORT:   int = 587
 
    class Config:
        env_file = ".env"
 
settings = Settings()
 