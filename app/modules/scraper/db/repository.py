from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.modules.scraper.data_models import HomePageData
from app.modules.scraper.db.schema import (
    ScrapeRun,
    ScrapedTender,
    ScrapedTenderFile,
    ScrapedTenderQuery,
)


class ScraperRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_scrape_run(self) -> Optional[ScrapeRun]:
        """
        Retrieves the most recent scrape run from the database, eagerly loading
        all related queries, tenders, and files.
        """
        return (
            self.db.query(ScrapeRun)
            .order_by(ScrapeRun.run_at.desc())
            .options(
                joinedload(ScrapeRun.queries)
                .joinedload(ScrapedTenderQuery.tenders)
                .joinedload(ScrapedTender.files)
            )
            .first()
        )

    def create_scrape_run(self, homepage_data: HomePageData) -> ScrapeRun:
        """
        Creates a new scrape run and all its related entities in the database
        from the provided Pydantic model.
        """
        scrape_run = ScrapeRun(
            date_str=homepage_data.header.date,
            name=homepage_data.header.name,
            contact=homepage_data.header.contact,
            no_of_new_tenders=homepage_data.header.no_of_new_tenders,
            company=homepage_data.header.company,
        )

        for query_data in homepage_data.query_table:
            scraped_query = ScrapedTenderQuery(
                query_name=query_data.query_name,
                number_of_tenders=query_data.number_of_tenders,
            )
            scrape_run.queries.append(scraped_query)

            for tender_data in query_data.tenders:
                scraped_tender = ScrapedTender(
                    tender_id_str=tender_data.tender_id,
                    tender_name=tender_data.tender_name,
                    tender_url=tender_data.tender_url,
                    dms_folder_id=tender_data.dms_folder_id,
                    city=tender_data.city,
                    summary=tender_data.summary,
                    value=tender_data.value,
                    due_date=tender_data.due_date,
                )

                if tender_data.details:
                    details = tender_data.details
                    # Notice
                    scraped_tender.tdr = details.notice.tdr
                    scraped_tender.tendering_authority = (
                        details.notice.tendering_authority
                    )
                    scraped_tender.tender_no = details.notice.tender_no
                    scraped_tender.tender_id_detail = details.notice.tender_id
                    scraped_tender.tender_brief = details.notice.tender_brief
                    scraped_tender.state = details.notice.state
                    scraped_tender.document_fees = details.notice.document_fees
                    scraped_tender.emd = details.notice.emd
                    scraped_tender.tender_value = details.notice.tender_value
                    scraped_tender.tender_type = details.notice.tender_type
                    scraped_tender.bidding_type = details.notice.bidding_type
                    scraped_tender.competition_type = details.notice.competition_type
                    # Details
                    scraped_tender.tender_details = details.details.tender_details
                    # Key Dates
                    scraped_tender.publish_date = details.key_dates.publish_date
                    scraped_tender.last_date_of_bid_submission = (
                        details.key_dates.last_date_of_bid_submission
                    )
                    scraped_tender.tender_opening_date = (
                        details.key_dates.tender_opening_date
                    )
                    # Contact Information
                    scraped_tender.company_name = (
                        details.contact_information.company_name
                    )
                    scraped_tender.contact_person = (
                        details.contact_information.contact_person
                    )
                    scraped_tender.address = details.contact_information.address
                    # Other Detail
                    scraped_tender.information_source = (
                        details.other_detail.information_source
                    )

                    for file_data in details.other_detail.files:
                        scraped_file = ScrapedTenderFile(
                            file_name=file_data.file_name,
                            file_url=file_data.file_url,
                            file_description=file_data.file_description,
                            file_size=file_data.file_size,
                        )
                        scraped_tender.files.append(scraped_file)

                scraped_query.tenders.append(scraped_tender)

        self.db.add(scrape_run)
        self.db.commit()
        self.db.refresh(scrape_run)
        return scrape_run
