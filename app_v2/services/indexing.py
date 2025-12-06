"""
Paper Indexing Service for Library Portal API V2

Pre-builds indexes for fast filtering and lookup.
"""

import logging
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict

from ..data_loader import DataLoader

logger = logging.getLogger(__name__)


class PaperIndex:
    """
    In-memory paper index for fast lookups.
    
    Pre-builds various indexes on load for efficient filtering:
    - By year
    - By semester
    - By course code
    - By program
    - By stream
    """
    
    def __init__(self):
        self.papers: List[Dict[str, Any]] = []
        self.loader: Optional[DataLoader] = None
        
        # Indexes for fast lookup
        self._by_year: Dict[int, List[Dict]] = defaultdict(list)
        self._by_semester: Dict[int, List[Dict]] = defaultdict(list)
        self._by_course: Dict[str, List[Dict]] = defaultdict(list)
        self._by_program: Dict[str, List[Dict]] = defaultdict(list)
        self._by_stream: Dict[str, List[Dict]] = defaultdict(list)
        
        # Unique values for metadata
        self._unique_years: Set[int] = set()
        self._unique_semesters: Set[int] = set()
        self._unique_course_codes: Set[str] = set()
        self._unique_programs: Set[str] = set()
        self._unique_degree_types: Set[str] = set()
        self._unique_paper_types: Set[str] = set()
        self._unique_streams: Set[str] = set()
        
        # Count aggregations
        self._count_by_year: Dict[int, int] = {}
        self._count_by_semester: Dict[int, int] = {}
        self._count_by_program: Dict[str, int] = {}
        
        # Stats
        self._files_loaded: int = 0
    
    def load_from_directory(self, loader: DataLoader) -> None:
        """Load papers from data loader and build indexes."""
        self.loader = loader
        self.papers = loader.load_all()
        self._build_indexes()
        
        stats = loader.get_stats()
        self._files_loaded = stats.get('files_loaded', 0)
        
        logger.info(f"Indexed {len(self.papers)} papers")
    
    def _build_indexes(self) -> None:
        """Build all indexes from loaded papers."""
        # Clear existing indexes
        self._by_year.clear()
        self._by_semester.clear()
        self._by_course.clear()
        self._by_program.clear()
        self._by_stream.clear()
        
        self._unique_years.clear()
        self._unique_semesters.clear()
        self._unique_course_codes.clear()
        self._unique_programs.clear()
        self._unique_degree_types.clear()
        self._unique_paper_types.clear()
        self._unique_streams.clear()
        
        # Build indexes
        for paper in self.papers:
            # Year index
            year = paper.get('year')
            if year:
                self._by_year[year].append(paper)
                self._unique_years.add(year)
            
            # Semester index
            semester = paper.get('semester')
            if semester:
                self._by_semester[semester].append(paper)
                self._unique_semesters.add(semester)
            
            # Course index
            course_code = paper.get('course_code')
            if course_code:
                self._by_course[course_code].append(paper)
                self._unique_course_codes.add(course_code)
            
            # Program index
            program = paper.get('degree_type') or paper.get('program')
            if program:
                self._by_program[program].append(paper)
                self._unique_programs.add(program)
            
            # Degree type
            degree_type = paper.get('degree_type')
            if degree_type:
                self._unique_degree_types.add(degree_type)
            
            # Paper type
            paper_type = paper.get('paper_type')
            if paper_type:
                self._unique_paper_types.add(paper_type)
            
            # Stream index
            streams = paper.get('streams') or []
            for stream in streams:
                self._by_stream[stream].append(paper)
                self._unique_streams.add(stream)
        
        # Build count aggregations
        self._count_by_year = {year: len(papers) for year, papers in self._by_year.items()}
        self._count_by_semester = {sem: len(papers) for sem, papers in self._by_semester.items()}
        self._count_by_program = {prog: len(papers) for prog, papers in self._by_program.items()}
        
        logger.debug(f"Built indexes: {len(self._unique_years)} years, "
                    f"{len(self._unique_course_codes)} courses, "
                    f"{len(self._unique_programs)} programs")
    
    # ==========================================================================
    # LOOKUP METHODS
    # ==========================================================================
    
    def get_by_year(self, year: int) -> List[Dict[str, Any]]:
        """Get papers for a specific year."""
        return self._by_year.get(year, [])
    
    def get_by_semester(self, semester: int) -> List[Dict[str, Any]]:
        """Get papers for a specific semester."""
        return self._by_semester.get(semester, [])
    
    def get_by_course(self, course_code: str) -> List[Dict[str, Any]]:
        """Get papers for a specific course code."""
        return self._by_course.get(course_code.upper(), [])
    
    def get_by_program(self, program: str) -> List[Dict[str, Any]]:
        """Get papers for a specific program."""
        return self._by_program.get(program, [])
    
    def get_by_stream(self, stream: str) -> List[Dict[str, Any]]:
        """Get papers for a specific stream."""
        return self._by_stream.get(stream, [])
    
    # ==========================================================================
    # PROPERTY ACCESSORS
    # ==========================================================================
    
    @property
    def total_papers(self) -> int:
        return len(self.papers)
    
    @property
    def files_loaded(self) -> int:
        return self._files_loaded
    
    @property
    def unique_years(self) -> List[int]:
        return sorted(self._unique_years, reverse=True)
    
    @property
    def unique_semesters(self) -> List[int]:
        return sorted(self._unique_semesters)
    
    @property
    def unique_course_codes(self) -> List[str]:
        return sorted(self._unique_course_codes)
    
    @property
    def unique_programs(self) -> List[str]:
        return sorted(self._unique_programs)
    
    @property
    def unique_degree_types(self) -> List[str]:
        return sorted(self._unique_degree_types)
    
    @property
    def unique_paper_types(self) -> List[str]:
        return sorted(self._unique_paper_types)
    
    @property
    def unique_streams(self) -> List[str]:
        return sorted(self._unique_streams)
    
    @property
    def count_by_year(self) -> Dict[int, int]:
        return dict(sorted(self._count_by_year.items(), reverse=True))
    
    @property
    def count_by_semester(self) -> Dict[int, int]:
        return dict(sorted(self._count_by_semester.items()))
    
    @property
    def count_by_program(self) -> Dict[str, int]:
        return dict(sorted(self._count_by_program.items(), key=lambda x: x[1], reverse=True))


# Global paper index instance
paper_index = PaperIndex()
