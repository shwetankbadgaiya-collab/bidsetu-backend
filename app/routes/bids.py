import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.db import get_db
from app.models.models import Bid, Bidder, Tender
from app.schemas.schemas import BidOut
from app.services.audit import log_action
from app.routes.auth import get_current_user

router = APIRouter()

@router.post("/", response_model=BidOut)
def create_bid(bidder_id: int, tender_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    bid_id = f"BID{random.randint(100, 999):03d}"
    
    db_bid = Bid(
        bid_id=bid_id,
        bidder_id=bidder_id,
        tender_id=tender_id,
    )
    db.add(db_bid)
    db.commit()
    db.refresh(db_bid)
    
    log_action(db, current_user['id'], 'Created Bid', 'bid', bid_id, f"Created bid for bidder {bidder_id} and tender {tender_id}")
    
    bidder = db.query(Bidder).filter(Bidder.id == bidder_id).first()
    bid_out = BidOut.model_validate(db_bid)
    if bidder:
        bid_out.bidder_name = bidder.name
        bid_out.company_name = bidder.company_name
    return bid_out

@router.get("/", response_model=List[BidOut])
def get_bids(tender_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Bid, Bidder).join(Bidder, Bid.bidder_id == Bidder.id)
    if tender_id:
        query = query.filter(Bid.tender_id == tender_id)
        
    results = []
    for bid, bidder in query.all():
        bid_out = BidOut.model_validate(bid)
        bid_out.bidder_name = bidder.name
        bid_out.company_name = bidder.company_name
        results.append(bid_out)
    return results

@router.get("/{bid_id}", response_model=BidOut)
def get_bid(bid_id: str, db: Session = Depends(get_db)):
    result = db.query(Bid, Bidder).join(Bidder, Bid.bidder_id == Bidder.id).filter(Bid.bid_id == bid_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Bid not found")
    
    bid, bidder = result
    bid_out = BidOut.model_validate(bid)
    bid_out.bidder_name = bidder.name
    bid_out.company_name = bidder.company_name
    return bid_out
