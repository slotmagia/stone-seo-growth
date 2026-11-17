from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import Product, Keyword, Content, Metric

def dashboard(db:Session) -> dict:
    return {
        "products":db.scalar(select(func.count(Product.id))) or 0,
        "keywords":db.scalar(select(func.count(Keyword.id))) or 0,
        "contents":db.scalar(select(func.count(Content.id))) or 0,
        "published_confirmed":db.scalar(select(func.count(Content.id)).where(Content.status=="PUBLISHED")) or 0,
        "impressions":db.scalar(select(func.coalesce(func.sum(Metric.impressions),0))) or 0,
        "clicks":db.scalar(select(func.coalesce(func.sum(Metric.clicks),0))) or 0,
        "qualified_leads":db.scalar(select(func.coalesce(func.sum(Metric.qualified_leads),0))) or 0,
        "orders":db.scalar(select(func.coalesce(func.sum(Metric.orders),0))) or 0,
        "metrics_note":"Only user-imported or separately authorized performance records are counted; none are inferred.",
    }
