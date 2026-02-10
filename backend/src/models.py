"""
SQLAlchemy ORM models for the database.
Defines schemas for: RepoAnalysis, User, UserAnalysisHistory, and ChatSession.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database import Base


class RepoAnalysis(Base):
    """
    Stores cached analysis results for repositories.
    Prevents redundant computation for popular repos.
    """
    __tablename__ = "repo_analysis"

    id = Column(Integer, primary_key=True, index=True)
    repo_url = Column(String(500), unique=True, index=True, nullable=False)
    branch = Column(String(100), default="main")
    
    # Cached AST and git analysis as JSONB (fast retrieval)
    repo_analysis = Column(JSON, nullable=True, doc="Cached AST parsing results")
    git_analysis = Column(JSON, nullable=True, doc="Cached git history analysis")
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    analysis_histories = relationship("UserAnalysisHistory", back_populates="repo_analysis")

    def __repr__(self):
        return f"<RepoAnalysis(repo_url={self.repo_url}, branch={self.branch})>"


class User(Base):
    """
    Stores user information for authentication and tracking.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Account status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    analysis_histories = relationship("UserAnalysisHistory", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")

    def __repr__(self):
        return f"<User(email={self.email}, username={self.username})>"


class UserAnalysisHistory(Base):
    """
    Tracks analysis history per user.
    Links users to their analysis of repositories.
    """
    __tablename__ = "user_analysis_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    repo_analysis_id = Column(Integer, ForeignKey("repo_analysis.id"), nullable=False, index=True)
    
    # Custom notes by user
    notes = Column(Text, nullable=True)
    
    # Timestamp
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="analysis_histories")
    repo_analysis = relationship("RepoAnalysis", back_populates="analysis_histories")

    def __repr__(self):
        return f"<UserAnalysisHistory(user_id={self.user_id}, repo_id={self.repo_analysis_id})>"


class ChatSession(Base):
    """
    Stores chat history for AI conversations with TTL caching via Redis.
    This preserves conversation context across sessions.
    """
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    
    # Last code analyzed in this session
    last_code = Column(Text, nullable=True)
    
    # Message history (stored as JSON for flexibility)
    messages = Column(JSON, default=list, doc="List of {role, content} messages")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")

    def __repr__(self):
        return f"<ChatSession(user_id={self.user_id}, session_id={self.session_id})>"
