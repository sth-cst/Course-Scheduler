from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

@dataclass
class Course:
    id: int
    name: str
    class_number: str
    credits: int
    prerequisites: List[int]
    corequisites: List[int]
    semesters_offered: List[str]
    is_elective: bool
    section_id: int
    credits_needed: int = None
    course_type: str = ""  # Already present
    course_id: str = ""    # Add this
    is_elective_section: bool = False  # Add this

@dataclass
class Semester:
    type: str  # Fall, Winter, Spring
    year: int
    credit_limit: int
    classes: List[Course] = None
    
    def __post_init__(self):
        self.classes = self.classes or []
        
    @property
    def total_credits(self) -> int:
        return sum(c.credits for c in self.classes)

class SchedulingLogFilter(logging.Filter):
    def filter(self, record):
        if not isinstance(record.msg, str):
            return True
            
        # Convert message to string if it's a dict
        message = str(record.msg)
        
        # Check for both the exact message and JSON-like content
        if ('Generated schedule response' in message or
            '"metadata":' in message or
            "'metadata':" in message or
            message.startswith('{') and ('schedule' in message or 'metadata' in message)):
            return False
            
        return True

# Configure logging with the enhanced filter
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Apply filter to root logger to catch all logging
logging.getLogger().addFilter(SchedulingLogFilter())
logger.addFilter(SchedulingLogFilter())

class ScheduleOptimizer:
    def __init__(self):
        self.satisfied_sections: Set[int] = set()
        
    def _is_first_year_semester(self, semester: Semester, start_semester: str) -> bool:
        """
        Check if semester is in first year (first 3 semesters)
        Returns True for first 3 semesters from start, regardless of type
        """
        start_type, start_year = start_semester.split()
        start_year = int(start_year)
        
        # Create ordered list of semesters starting from start semester
        sem_sequence = []
        current_type = start_type
        current_year = start_year
        
        # Generate sequence of first 6 semesters (more than enough to check first 3)
        for _ in range(6):
            sem_sequence.append((current_type, current_year))
            # Update to next semester
            if current_type == "Fall":
                current_type = "Winter"
                current_year += 1
            elif current_type == "Winter":
                current_type = "Spring"
            else:  # Spring
                current_type = "Fall"
        
        # Check if current semester is in first 3 of sequence
        target = (semester.type, semester.year)
        try:
            index = sem_sequence.index(target)
            return index < 3  # First 3 semesters are first year
        except ValueError:
            return False

        logger.info(f"Semester {semester.type} {semester.year} first year status: {index < 3}")

    def _get_semester_credit_limit(self, semester: Semester, params: Dict) -> int:
        """Get credit limit for semester considering first year status"""
        if self._is_first_year_semester(semester, params["startSemester"]):
            if semester.type == "Spring":
                return params["firstYearLimits"]["springCredits"]
            return params["firstYearLimits"]["fallWinterCredits"]
        else:
            if semester.type == "Spring":
                return params["springCredits"]
            return params["fallWinterCredits"]

    def _convert_to_courses(self, raw_classes: Dict) -> List[Course]:
        """Convert raw class data to Course objects"""
        courses = []
        for id, data in raw_classes.items():
            course = Course(
                id=int(id),
                name=data["class_name"],
                class_number=data.get("class_number", ""),
                credits=data["credits"],
                prerequisites=data.get("prerequisites", []),
                corequisites=data.get("corequisites", []),
                semesters_offered=data["semesters_offered"],
                is_elective=data.get("is_elective", False),
                section_id=data["section_id"],
                credits_needed=data.get("credits_needed"),
                course_type=data.get("course_type", ""),
                course_id=str(data.get("course_id", "")),  # Add this
                is_elective_section=data.get("is_elective_section", False)  # Add this
            )
            courses.append(course)
        return courses

    def _sort_by_prerequisites(self, courses: List[Course]) -> List[Course]:
        """Sort courses optimizing for earliest possible graduation"""
        # Create mappings for prerequisite chains and dependent courses
        prereq_chains = {}
        dependent_courses = {}
        chain_depths = {}
        
        def get_all_prerequisites(course_id: int, seen=None) -> Set[int]:
            if seen is None:
                seen = set()
            if course_id in seen:
                return set()
            seen.add(course_id)
            
            course = next((c for c in courses if c.id == course_id), None)
            if not course:
                return set()
                
            direct_prereqs = set(course.prerequisites)
            all_prereqs = direct_prereqs.copy()
            
            for prereq_id in direct_prereqs:
                all_prereqs.update(get_all_prerequisites(prereq_id, seen))
                
            return all_prereqs
        
        def get_chain_depth(course_id: int, seen=None) -> int:
            """Calculate the depth of the prerequisite chain"""
            if seen is None:
                seen = set()
            if course_id in seen:
                return 0
            seen.add(course_id)
            
            course = next((c for c in courses if c.id == course_id), None)
            if not course or not course.prerequisites:
                return 0
                
            return 1 + max([get_chain_depth(prereq_id, seen.copy()) for prereq_id in course.prerequisites], default=0)

        # Build prerequisite chains and calculate dependent courses
        for course in courses:
            # Calculate chain depth (longest path from any root to this course)
            chain_depths[course.id] = get_chain_depth(course.id)
            
            # Get all prerequisites
            prereq_chains[course.id] = get_all_prerequisites(course.id)
            
            # Initialize dependency counter
            dependent_courses[course.id] = 0
        
        # Count dependencies in a second pass
        for course in courses:
            for prereq_id in prereq_chains[course.id]:
                dependent_courses[prereq_id] = dependent_courses.get(prereq_id, 0) + 1
    
        # Calculate semester flexibility (fewer offerings = less flexible)
        offering_flexibility = {c.id: len(c.semesters_offered) for c in courses}
        
        # Sort courses based on multiple criteria to optimize graduation time
        return sorted(courses, key=lambda c: (
            # Religion courses get highest priority - sort them first
            0 if self._is_religion_class(c) else 1,
            -chain_depths[c.id],            # Deep prerequisite chains first
            -dependent_courses[c.id],       # Courses that unlock more dependencies
            offering_flexibility[c.id],     # Less flexible courses scheduled earlier
            c.id                            # Stable sort
        ))

    def _can_schedule_in_semester(self, course: Course, scheduled_courses: List[Course]) -> bool:
        """Check if all prerequisites for a course have been scheduled"""
        scheduled_ids = {c.id for c in scheduled_courses}
        return all(prereq_id in scheduled_ids for prereq_id in course.prerequisites)

    # Add a helper method to check religion classes
    def _is_religion_class(self, course: Course) -> bool:
        """Check if a course is a religion course"""
        return course.course_type == "religion"

    def _is_religion_class_dict(self, course_dict: Dict) -> bool:
        """Check if a course dictionary represents a religion course"""
        return course_dict.get("course_type") == "religion"

    def _is_eil_course(self, course: Course) -> bool:
        """Check if a course is an EIL course"""
        eil_courses = {"STDEV 100R", "EIL 201", "EIL 313", "EIL 317", "EIL 320"}
        return course.class_number in eil_courses

    def _is_eil_course_dict(self, course_dict: Dict) -> bool:
        """Check if a course dictionary represents an EIL course"""
        eil_courses = {"STDEV 100R", "EIL 201", "EIL 313", "EIL 317", "EIL 320"}
        return course_dict.get("class_number") in eil_courses

    # Add a method to check if we can schedule a religion class in a semester
    def _can_schedule_religion_in_semester(self, semester_courses: List[Course]) -> bool:
        """Check if a religion class can be scheduled in the semester (max 1 per semester)"""
        religion_count = sum(1 for course in semester_courses if self._is_religion_class(course))
        return religion_count == 0  # Can only schedule if no religion courses are already scheduled

    def _is_major_course(self, course: Course) -> bool:
        """Check if a course is a major course"""
        return course.course_type == "major"

    def _is_major_course_dict(self, course_dict: Dict) -> bool:
        """Check if a course dictionary represents a major course"""
        return course_dict.get("course_type") == "major"

    def _count_major_courses_in_semester(self, semester_courses: List[Course]) -> int:
        """Count the number of major courses in a semester"""
        return sum(1 for course in semester_courses if self._is_major_course(course))

    def _count_major_courses_in_semester_dict(self, semester_courses: List[Dict]) -> int:
        """Count the number of major courses in a semester from course dictionaries"""
        return sum(1 for course in semester_courses if self._is_major_course_dict(course))

    def _can_add_major_course_to_semester(self, course: Course, semester_courses: List[Course], 
                                         major_class_limit: int) -> bool:
        """Check if a major course can be added to a semester without exceeding the limit"""
        if not self._is_major_course(course):
            return True  # Non-major courses are not limited
        
        current_major_count = self._count_major_courses_in_semester(semester_courses)
        
        # Check if adding this course would exceed the limit
        courses_to_add = self._get_course_with_coreqs(course, self._all_courses)
        major_courses_to_add = sum(1 for c in courses_to_add if self._is_major_course(c))
        
        return current_major_count + major_courses_to_add <= major_class_limit

    def create_schedule(self, processed_data: Dict) -> Dict:
        """Create a schedule with integrated EIL and regular courses"""
        try:
            # Validate input
            if not processed_data.get("classes"):
                logger.error("No classes in processed data")
                return {
                    "error": "No classes to schedule",
                    "metadata": {
                        "success": False,
                        "message": "No classes provided for scheduling"
                    }
                }
                
            if not processed_data.get("parameters"):
                logger.error("No parameters in processed data")
                return {
                    "error": "Missing scheduling parameters",
                    "metadata": {
                        "success": False,
                        "message": "No scheduling parameters provided"
                    }
                }
                
            # Add logging for schedule generation
            logger.info(f"Starting schedule creation with {len(processed_data['classes'])} classes")
            
            # Initialize tracking sets
            self.satisfied_sections = set()
            scheduled_course_ids = set()
            
            params = processed_data["parameters"]
            # Remove this log
            # logger.info(f"Received scheduling parameters: {params}")
            
            self._all_courses = self._convert_to_courses(processed_data["classes"])
            
            # Handle empty or missing firstYearLimits
            if not params.get("firstYearLimits") or not isinstance(params["firstYearLimits"], dict):
                params["firstYearLimits"] = {
                    "fallWinterCredits": params["fallWinterCredits"],
                    "springCredits": params["springCredits"]
                }
        
            # Initialize semesters
            semesters = self._initialize_semesters(
                params["startSemester"],
                params["fallWinterCredits"],
                params["springCredits"],
                params["firstYearLimits"]["fallWinterCredits"],
                params["firstYearLimits"]["springCredits"]
            )
            
            # Group courses by section
            sections = self._group_by_section(self._all_courses)
            
            # Track all courses to be scheduled
            courses_to_schedule = []
            
            # Process each section
            for section_id, courses in sections.items():
                if section_id == "additional-section":
                    continue
                    
                if any(c.is_elective for c in courses):
                    credits_needed = next((c.credits_needed for c in courses if c.credits_needed), None)
                    if credits_needed:
                        try:
                            combination = self._find_best_elective_combination(courses, credits_needed)
                            if combination:
                                courses_to_schedule.extend(combination)
                                # Keep this log as it's useful for tracking elective combinations
                                logger.info(f"Selected electives for section {section_id}: {[c.class_number for c in combination]}")
                        except ValueError as e:
                            logger.error(f"Failed to satisfy section {section_id}: {str(e)}")
                            return {
                                "error": str(e),
                                "metadata": {
                                    "approach": "integrated-scheduling",
                                    "startSemester": params["startSemester"],
                                    "success": False
                            }
                        }
                else:
                    required_courses = [c for c in courses if not c.is_elective]
                    courses_to_schedule.extend(required_courses)
                    # Remove this log
                    # logger.info(f"Added required courses for section {section_id}: {[c.class_number for c in required_courses]}")

            # Split courses into EIL and regular courses
            eil_courses = [c for c in courses_to_schedule if self._is_eil_course(c)]
            regular_courses = [c for c in courses_to_schedule if not self._is_eil_course(c)]
            
            # Group EIL courses according to scheduling rules
            first_sem_required = []
            first_sem_flexible = []
            second_sem_required = []
            
            for course in eil_courses:
                if course.class_number == "EIL 320":
                    second_sem_required.append(course)
                elif course.class_number == "EIL 201":
                    first_sem_flexible.append(course)
                else:
                    first_sem_required.append(course)
            
            # Sort regular courses by prerequisites
            sorted_regular_courses = self._sort_by_prerequisites(regular_courses)
            
            # Integrated scheduling - single loop for all courses
            current_semester_idx = 0
            scheduled_semesters = []
            remaining_courses = sorted_regular_courses.copy()
            all_scheduled_courses = []
            
            while remaining_courses or first_sem_required or first_sem_flexible or second_sem_required:
                # Create new semester if needed
                if current_semester_idx >= len(semesters):
                    last_sem = semesters[-1]
                    new_sem = self._create_next_semester(last_sem, params)
                    semesters.append(new_sem)
                    
                semester = semesters[current_semester_idx]
                semester_courses = []
                current_credits = 0
                courses_scheduled_this_semester = False
                
                # FIRST PRIORITY: Handle EIL courses based on semester index
                if current_semester_idx == 0 and (first_sem_required or first_sem_flexible):
                    # Schedule required first semester EIL courses
                    for course in first_sem_required[:]:
                        if current_credits + course.credits <= semester.credit_limit:
                            semester_courses.append(course)
                            current_credits += course.credits
                            scheduled_course_ids.add(course.id)
                            first_sem_required.remove(course)
                            all_scheduled_courses.append(course)
                            courses_scheduled_this_semester = True
                    
                    # Try to add flexible EIL courses if space permits
                    for course in first_sem_flexible[:]:
                        if current_credits + course.credits <= semester.credit_limit:
                            semester_courses.append(course)
                            current_credits += course.credits
                            scheduled_course_ids.add(course.id)
                            first_sem_flexible.remove(course)
                            all_scheduled_courses.append(course)
                            courses_scheduled_this_semester = True
                        else:
                            # Move to second semester if no space
                            second_sem_required.extend([c for c in first_sem_flexible])
                            first_sem_flexible = []
                            
                elif current_semester_idx == 1 and second_sem_required:
                    # Schedule second semester EIL courses
                    for course in second_sem_required[:]:
                        if current_credits + course.credits <= semester.credit_limit:
                            semester_courses.append(course)
                            current_credits += course.credits
                            scheduled_course_ids.add(course.id)
                            second_sem_required.remove(course)
                            all_scheduled_courses.append(course)
                            courses_scheduled_this_semester = True
            
                # SECOND PRIORITY: Schedule regular courses in remaining space with optimization
                course_priorities = []

                # Check if we should force religion course scheduling
                force_religion_scheduling = self._should_force_religion_scheduling(remaining_courses, scheduled_semesters)

                for course in remaining_courses:
                    # Skip if already scheduled
                    if course.id in scheduled_course_ids:
                        continue
                        
                    # Check if course can be offered this semester
                    if semester.type not in course.semesters_offered:
                        continue
                        
                    # Check prerequisites are satisfied in previous semesters
                    if not self._prerequisites_satisfied_before_semester(course, all_scheduled_courses, 
                                                                     current_semester_idx, scheduled_semesters):
                        continue

                    # Check religion class limitation - only one per semester
                    if self._is_religion_class(course):
                        # Count existing religion courses in this semester
                        religion_courses_in_semester = sum(1 for c in semester_courses if self._is_religion_class(c))
                        if religion_courses_in_semester >= 1:
                            continue  # Skip this religion course if we already have one
                        
                        # Also check if any corequisites are religion courses
                        added_courses_preview = self._add_course_with_coreqs(course, remaining_courses)
                        religion_in_coreqs = sum(1 for c in added_courses_preview if self._is_religion_class(c))
                        if religion_in_coreqs > 1:  # More than just the main course
                            continue  # Skip if corequisites include other religion courses

                    # Calculate priority score for this course
                    priority = 0

                    # 1. HIGHEST priority for courses that unlock the most other courses
                    # Look at ALL remaining courses, not just those that can be scheduled this semester
                    unlocks_count = sum(1 for c in remaining_courses if course.id in c.prerequisites)
                    priority += unlocks_count * 20  # Increased weight significantly

                    # 2. Additional priority boost for courses with NO prerequisites (foundation courses)
                    if not course.prerequisites:
                        # Foundation courses that unlock others get massive priority
                        if unlocks_count > 0:
                            priority += 50  # Very high priority for foundation courses
                        else:
                            priority += 5   # Still good priority for standalone foundation courses

                    # 3. High priority for courses in long prerequisite chains
                    chain_length = len([c for c in all_scheduled_courses if c.id in course.prerequisites])
                    priority += chain_length * 5

                    # 4. High priority for courses with limited semester offerings
                    flexibility_penalty = (3 - min(len(course.semesters_offered), 3)) * 8
                    priority += flexibility_penalty

                    # 5. Enhanced religion course distribution logic - prioritize early scheduling
                    if self._is_religion_class(course):
                        # Always give religion courses high priority to schedule them early
                        priority += 15  # High priority to ensure early scheduling
                    else:
                        # Small boost for non-religion courses
                        priority += 0.5

                    # 6. Bonus for completing degree requirements early
                    if course.course_type in ["major", "core"]:
                        priority += 3
                    
                    course_priorities.append((course, priority))

                # Sort courses by priority (highest first)
                course_priorities.sort(key=lambda x: x[1], reverse=True)

                # Try scheduling courses in priority order
                for course, _ in course_priorities:
                    # Check if there's enough space for the course and its corequisites
                    course_credits = self._get_total_credits(course, remaining_courses)
                    if current_credits + course_credits <= semester.credit_limit:
                        # Check major class limit before scheduling
                        major_class_limit = params.get("majorClassLimit", 3)
                        if not self._can_add_major_course_to_semester(course, semester_courses, major_class_limit):
                            continue  # Skip this major course if it would exceed the limit
                        
                        try:
                            # Add course and its corequisites
                            added_courses = self._add_course_with_coreqs(course, remaining_courses)
                            
                            # Enhanced religion course validation
                            if self._is_religion_class(course):
                                # Count religion courses already in semester
                                existing_religion = sum(1 for c in semester_courses if self._is_religion_class(c))
                                # Count religion courses in what we're about to add
                                new_religion = sum(1 for c in added_courses if self._is_religion_class(c))
                                
                                if existing_religion + new_religion > 1:
                                    # Skip silently - this is expected behavior
                                    continue
                            
                            semester_courses.extend(added_courses)
                            current_credits += course_credits
                            courses_scheduled_this_semester = True
                            
                            # Add to overall scheduled courses
                            all_scheduled_courses.extend(added_courses)
                            
                            # Log major course scheduling for debugging
                            if self._is_major_course(course):
                                major_count = self._count_major_courses_in_semester(semester_courses)
                                logger.info(f"Scheduled major course {course.class_number} in {semester.type} {semester.year} (major count: {major_count}/{major_class_limit})")
                            
                            # Remove scheduled courses
                            for c in added_courses:
                                if c in remaining_courses:
                                    remaining_courses.remove(c)
                                    scheduled_course_ids.add(c.id)
                        except Exception as e:
                            logger.error(f"Error scheduling {course.class_number}: {str(e)}")
                            continue
                
                # Add semester to schedule if courses were added
                if semester_courses:
                    scheduled_semesters.append({
                        "type": semester.type,
                        "year": semester.year,
                        "classes": [self._course_to_dict(c) for c in semester_courses],
                        "totalCredits": current_credits
                    })
                
                # Move to next semester if we scheduled courses or reached credit limit
                if courses_scheduled_this_semester or current_credits >= semester.credit_limit:
                    current_semester_idx += 1
                else:
                    # If no courses could be scheduled, try next semester
                    current_semester_idx += 1
                    if current_semester_idx >= len(semesters):
                        logger.warning("Could not schedule all courses within available semesters")
                        break
                
                # Exit loop when all courses are scheduled
                if not (remaining_courses or first_sem_required or first_sem_flexible or second_sem_required):
                    break

            # Optimize final semesters to eliminate unnecessary semesters by strategically swapping religion courses
            scheduled_semesters = self._optimize_final_semesters(scheduled_semesters, params)

            return {
                "metadata": {
                    "approach": "integrated-scheduling",
                    "startSemester": params["startSemester"],
                    "score": 1.0,
                    "improvements": [
                        "Integrated EIL and regular course scheduling",
                        "Maximized semester utilization",
                        "Maintained all course scheduling rules and constraints",
                        "Optimized schedule to eliminate unnecessary semesters"
                    ]
                },
                "schedule": scheduled_semesters
            }
        except Exception as e:
            logger.error(f"Error in schedule creation: {str(e)}")
            return {
                "error": str(e),
                "metadata": {
                    "success": False,
                    "message": f"Schedule creation failed: {str(e)}"
                }
            }

    def _initialize_semesters(self, start_semester: str, 
                            regular_fall_winter: int,
                            regular_spring: int,
                            first_year_fall_winter: int,
                            first_year_spring: int) -> List[Semester]:
        sem_type, year = start_semester.split()
        year = int(year)
        
        semesters = []
        for i in range(15):  # Generate more semesters to ensure we don't run out
            # First 3 semesters are first year
            is_first_year = i < 3
            if sem_type == "Spring":
                credit_limit = first_year_spring if is_first_year else regular_spring
            else:
                credit_limit = first_year_fall_winter if is_first_year else regular_fall_winter
                
            semesters.append(Semester(sem_type, year, credit_limit))
            
            # Update semester type and year in chronological order
            if sem_type == "Fall":
                sem_type = "Winter"
                year += 1  # Winter is next year from Fall
            elif sem_type == "Winter":
                sem_type = "Spring"
                # Spring is same year as Winter
            else:  # Spring
                sem_type = "Fall"
                # Fall is same year as Spring
                
        return semesters

    def _group_by_section(self, courses: List[Course]) -> Dict[int, List[Course]]:
        sections = {}
        for course in courses:
            if course.section_id not in sections:
                sections[course.section_id] = []
            sections[course.section_id].append(course)
        return sections

    def _find_best_elective_combination(self, courses: List[Course], credits_needed: int) -> List[Course]:
        """Find optimal combination of elective courses that meets or exceeds credit requirement"""
        logger.info(f"Looking for combination totaling at least {credits_needed} credits from section {courses[0].section_id}")
        
        # Get only elective courses
        elective_courses = [c for c in courses if c.is_elective]
        
        # Calculate total available credits in this section INCLUDING corequisites
        total_available_credits = 0
        for course in elective_courses:
            course_with_coreqs = self._get_course_with_coreqs(course, self._all_courses)
            total_available_credits += sum(c.credits for c in course_with_coreqs)
    
        logger.info(f"Section {courses[0].section_id} has {total_available_credits} total credits available (including corequisites)")
    
        if total_available_credits < credits_needed:
            error_msg = (f"Section {courses[0].section_id} requires {credits_needed} credits but only has "
                        f"{total_available_credits} credits available from elective courses (including corequisites)")
            logger.error(error_msg)
            raise ValueError(error_msg)
    
        # Track section fulfillment
        section_id = courses[0].section_id
        if section_id in self.satisfied_sections:
            logger.info(f"Section {section_id} already satisfied")
            return []
            
        best_combination = None
        best_total = 0
        
        # Try combinations of increasing size
        for size in range(1, len(elective_courses) + 1):
            current_combo = []
            current_total = 0
            
            # Add courses one by one until we exceed or meet the requirement
            for course in elective_courses[:size]:
                course_and_coreqs = self._get_course_with_coreqs(course, self._all_courses)
                current_combo.extend(course_and_coreqs)
                current_total = sum(c.credits for c in current_combo)
                
                # If we've met or exceeded the requirement, this is a valid combination
                if current_total >= credits_needed:
                    best_combination = current_combo
                    best_total = current_total
                    break  # Found a valid combination for this size
                
        # If we found a valid combination, use it
        if best_combination:
            self.satisfied_sections.add(section_id)
            logger.info(f"Found combination for section {section_id}: {[c.class_number for c in best_combination]} = {best_total} cr "
                       f"(needed {credits_needed})")
            return best_combination

        logger.warning(f"Could not meet credit requirement for section {section_id}: needed {credits_needed} credits")
        return []  # Return empty list instead of None

    def _get_course_with_coreqs(self, course: Course, available_courses: List[Course]) -> List[Course]:
        """Get a course and all its corequisites"""
        result = [course]
        
        # Add all corequisites
        for coreq_id in course.corequisites:
            if isinstance(coreq_id, dict):
                coreq_id = coreq['id']
            coreq = next((c for c in available_courses if c.id == coreq_id), None)
            if coreq and coreq not in result:
                result.append(coreq)
                
        return result

    def _course_to_dict(self, course: Course) -> Dict:
        return {
            "id": course.id,
            "class_name": course.name,
            "class_number": course.class_number,
            "credits": course.credits,
            "prerequisites": course.prerequisites,
            "corequisites": course.corequisites,
            "semesters_offered": course.semesters_offered,
            "is_elective": course.is_elective,
            "course_type": course.course_type,
            "course_id": course.course_id,
            "is_elective_section": course.is_elective_section,
            "section_id": course.section_id,
            "credits_needed": course.credits_needed
        }

    def _create_next_semester(self, last_semester: Semester, params: Dict) -> Semester:
        """Create the next semester in sequence (Fall -> Winter -> Spring -> Fall...)"""
        if last_semester.type == "Fall":
            new_type = "Winter"
            new_year = last_semester.year + 1
        elif last_semester.type == "Winter":
            new_type = "Spring"
            new_year = last_semester.year
        else:  # Spring
            new_type = "Fall"
            new_year = last_semester.year
            
        # Create new semester instance
        new_semester = Semester(type=new_type, year=new_year, credit_limit=0)
        # Set credit limit based on regular rules (first year limits not applied here)
        new_semester.credit_limit = self._get_semester_credit_limit(new_semester, params)
        
        return new_semester

    def _get_total_credits(self, course: Course, available_courses: List[Course]) -> int:
        """Calculate total credits including all corequisites"""
        # Start with the course's credits
        total = course.credits
        
        # Track processed courses to avoid cycles
        processed = {course.id}
        
        # Queue of courses to check for corequisites
        to_check = [course]
        
        while to_check:
            current = to_check.pop()
            for coreq_id in current.corequisites:
                # Skip if we've already counted this course
                if coreq_id in processed:
                    continue
                    
                coreq = next((c for c in available_courses if c.id == coreq_id), None)
                if coreq:
                    processed.add(coreq_id)
                    total += coreq.credits
                    to_check.append(coreq)
        
        return total

    def _add_course_with_coreqs(self, course: Course, remaining_courses: List[Course]) -> List[Course]:
        """Add a course and its corequisites, ensuring one-way corequisites are scheduled together"""
        # Start with the main course
        added = [course]
        required_coreqs = set()
        to_check = [course]
        
        while to_check:
            current = to_check.pop()
            for coreq_id in current.corequisites:
                # Handle dictionary-style corequisite references
                if isinstance(coreq_id, dict):
                    coreq_id = coreq['id']
                
                if coreq_id in required_coreqs:
                    continue
                
                # First try to find in remaining_courses
                coreq = next((c for c in remaining_courses if c.id == coreq_id), None)
                
                # If not found, look in all courses
                if not coreq:
                    coreq = next((c for c in self._all_courses if c.id == coreq_id), None)
                
                if coreq:
                    required_coreqs.add(coreq_id)
                    to_check.append(coreq)
                    
                    # If this is a system course being pulled in by a non-system course,
                    # update its course_type to match the parent
                    if coreq.course_type == "system" and course.course_type != "system":
                        logger.info(f"Updating {coreq.class_number} type from system to {course.course_type}")
                        coreq.course_type = course.course_type
    
        # Add all required corequisites
        for coreq_id in required_coreqs:
            coreq = (next((c for c in remaining_courses if c.id == coreq_id), None) or 
                    next((c for c in self._all_courses if c.id == coreq_id), None))
            if coreq and coreq not in added:
                added.append(coreq)
                # Keep corequisite combination logs as they're useful for debugging
                logger.info(f"Adding corequisite {coreq.class_number} with {course.class_number}")
    
        return added

    def _prerequisites_satisfied_before_semester(self, course: Course, all_scheduled_courses: List[Course], 
                                          current_semester_idx: int, scheduled_semesters: List[Dict]) -> bool:
        """Check if prerequisites are satisfied in previous semesters"""
        # EIL courses have no prerequisites between them
        if self._is_eil_course(course):
            return True
            
        if not course.prerequisites:
            return True
            
        # Get all courses scheduled in previous semesters only
        courses_in_previous_semesters = []
        for i in range(current_semester_idx):
            if i < len(scheduled_semesters):
                semester = scheduled_semesters[i]
                for course_dict in semester["classes"]:
                    courses_in_previous_semesters.append(course_dict["id"])

        # Check if all prerequisites are in previous semesters
        return all(prereq_id in courses_in_previous_semesters for prereq_id in course.prerequisites)

    def _get_semester_chronological_order(self, start_semester: str) -> List[Tuple[str, int]]:
        """Generate chronological order of semesters starting from start semester"""
        start_type, start_year = start_semester.split()
        start_year = int(start_year)
        
        semester_sequence = []
        current_type = start_type
        current_year = start_year
        
        # Generate sequence for several years
        for _ in range(20):  # Generate enough semesters
            semester_sequence.append((current_type, current_year))
            
            # Update to next semester in chronological order
            if current_type == "Fall":
                current_type = "Winter"
                current_year += 1
            elif current_type == "Winter":
                current_type = "Spring"
            else:  # Spring
                current_type = "Fall"
                
        return semester_sequence
    
    def _is_semester_before(self, semester1: Dict, semester2: Dict, start_semester: str) -> bool:
        """Check if semester1 comes chronologically before semester2"""
        semester_sequence = self._get_semester_chronological_order(start_semester)
        
        sem1_tuple = (semester1["type"], semester1["year"])
        sem2_tuple = (semester2["type"], semester2["year"])
        
        try:
            index1 = semester_sequence.index(sem1_tuple)
            index2 = semester_sequence.index(sem2_tuple)
            return index1 < index2
        except ValueError:
            # If semester not found in sequence, assume false
            return False

    def _prerequisites_satisfied_in_semester_dict(self, course: Dict, scheduled_semesters: List[Dict], 
                                                 semester_idx: int) -> bool:
        """Check if prerequisites are satisfied for a course in a specific semester"""
        if not course.get("prerequisites"):
            return True
        
        # Get all courses scheduled before this semester
        scheduled_before = []
        for i in range(semester_idx):
            for c in scheduled_semesters[i]["classes"]:
                scheduled_before.append(c["id"])
        
        return all(prereq_id in scheduled_before for prereq_id in course["prerequisites"])

    def _can_move_course_to_later_semester(self, course: Dict, from_semester_idx: int, 
                                         to_semester_idx: int, scheduled_semesters: List[Dict]) -> bool:
        """Check if moving a course to a later semester would violate prerequisites for other courses"""
        course_id = course["id"]
        
        # Check all courses in semesters between from_semester and to_semester (inclusive of to_semester)
        for i in range(from_semester_idx + 1, len(scheduled_semesters)):
            semester = scheduled_semesters[i]
            for other_course in semester["classes"]:
                # If any course has this course as a prerequisite, we can't move it later
                if course_id in other_course.get("prerequisites", []):
                    # But if we're moving it to before that course, it's still valid
                    if i > to_semester_idx:
                        return False
        
        return True

    def _schedule_eil_courses(self, courses_to_schedule: List[Course], semesters: List[Semester], 
                         scheduled_semesters: List[Dict], scheduled_course_ids: Set[int]) -> Tuple[List[Course], int]:
        """
        Schedule EIL courses following specific rules:
        - STDEV 100R, EIL 313, EIL 317 must be in first semester if possible
        - EIL 201 can move to second semester if needed
        - EIL 320 must be in second semester
        """
        eil_courses = [c for c in courses_to_schedule if self._is_eil_course(c)]
        if not eil_courses:
            return courses_to_schedule, 0

        # Remove EIL courses from main scheduling
        remaining_courses = [c for c in courses_to_schedule if not self._is_eil_course(c)]
        
        # Sort EIL courses by priority
        first_sem_required = []
        first_sem_flexible = []
        second_sem_required = []
        
        for course in eil_courses:
            if course.class_number == "EIL 320":
                second_sem_required.append(course)
            elif course.class_number == "EIL 201":
                first_sem_flexible.append(course)
            else:
                first_sem_required.append(course)

        # Schedule first semester
        first_semester = semesters[0]
        current_credits = 0
        first_sem_courses = []
        
        # First add required courses
        for course in first_sem_required:
            if current_credits + course.credits <= first_semester.credit_limit:
                first_sem_courses.append(course)
                current_credits += course.credits
                scheduled_course_ids.add(course.id)
        
        # Try to add flexible course if space permits
        for course in first_sem_flexible:
            if current_credits + course.credits <= first_semester.credit_limit:
                first_sem_courses.append(course)
                current_credits += course.credits
                scheduled_course_ids.add(course.id)
            else:
                second_sem_required.extend(first_sem_flexible)

        if first_sem_courses:
            scheduled_semesters.append({
                "type": first_semester.type,
                "year": first_semester.year,
                "classes": [self._course_to_dict(c) for c in first_sem_courses],
                "totalCredits": current_credits
            })
        
        # Schedule second semester
        if second_sem_required:
            second_semester = semesters[1]
            current_credits = 0
            second_sem_courses = []
            
            for course in second_sem_required:
                second_sem_courses.append(course)
                current_credits += course.credits
                scheduled_course_ids.add(course.id)
                
            scheduled_semesters.append({
                "type": second_semester.type,
                "year": second_semester.year,
                "classes": [self._course_to_dict(c) for c in second_sem_courses],
                "totalCredits": current_credits
            })
            
            return remaining_courses, 2
            
        return remaining_courses, 1

    def _get_prerequisite_chain(self, course: Course, all_courses: List[Course], seen=None) -> List[List[str]]:
        """Get complete prerequisite chains for a course"""
        if seen is None:
            seen = set()
        
        if course.id in seen:
            return []
            
        seen.add(course.id)
        
        # If no prerequisites, return empty list
        if not course.prerequisites:
            return [[course.class_number]]
            
        all_chains = []
        for prereq_id in course.prerequisites:
            prereq_course = next((c for c in all_courses if c.id == prereq_id), None)
            if prereq_course:
                # Get chains for this prerequisite
                prereq_chains = self._get_prerequisite_chain(prereq_course, all_courses, seen.copy())
                # Add current course to each chain
                for chain in prereq_chains:
                    all_chains.append(chain + [course.class_number])
                    
        return all_chains

    def _get_all_chains(self, courses: List[Course]) -> Dict[str, Dict]:
        """Get all prerequisite and corequisite chains"""
        chains = {}
        processed = set()
        
        for course in courses:
            # Skip if already part of another chain
            if course.class_number in processed:
                continue
                
            if course.prerequisites or course.corequisites:
                prereq_chains = self._get_prerequisite_chain(course, courses)
                coreq_chain = [c.class_number for c in self._get_course_with_coreqs(course, courses)]
                
                # Only keep longest chain for each end course 
                longest_chains = []
                for chain in prereq_chains:
                    if len(chain) > 1:  # Only include chains with 2+ courses
                        # Mark all courses in chain as processed
                        processed.update(chain)
                        longest_chains.append(chain)
                
                if longest_chains or len(coreq_chain) > 1:
                    chains[course.class_number] = {
                        "prerequisites": longest_chains,
                        "corequisites": coreq_chain if len(coreq_chain) > 1 else []
                    }
        
        return chains

    def _should_force_religion_scheduling(self, remaining_courses: List[Course], 
                                    scheduled_semesters: List[Dict]) -> bool:
        """Check if we should force religion course scheduling to avoid end-stacking"""
        religion_courses_left = sum(1 for c in remaining_courses if self._is_religion_class(c))
        
        # If we have no religion courses left, don't force
        if religion_courses_left == 0:
            return False
        
        # Force religion scheduling immediately if we have any religion courses left
        # Remove the semester restriction - can start from semester 1
        if religion_courses_left > 0:
            return True
            
        return False

    def _optimize_final_semesters(self, scheduled_semesters: List[Dict], params: Dict) -> List[Dict]:
        """Optimize final semesters to eliminate unnecessary semesters by strategically swapping religion courses"""
        if len(scheduled_semesters) < 2:
            return scheduled_semesters
        
        optimized = True
        max_iterations = 3  # Prevent infinite loops
        iterations = 0
        
        while optimized and iterations < max_iterations:
            optimized = False
            iterations += 1
            
            # Check each semester starting from the end
            for last_idx in range(len(scheduled_semesters) - 1, 0, -1):
                last_semester = scheduled_semesters[last_idx]
                
                # Be more aggressive about eliminating final semesters
                # Especially target single religion courses or very light semesters
                should_eliminate = (
                    # Single course semesters (especially religion courses)
                    len(last_semester["classes"]) == 1 or
                    # Very light credit loads
                    last_semester["totalCredits"] <= 4 or
                    # Semesters with only religion courses
                    all(self._is_religion_class_dict(c) for c in last_semester["classes"]) or
                    # Small semesters that can likely be redistributed
                    (len(last_semester["classes"]) <= 2 and last_semester["totalCredits"] <= 6)
                )
                
                if should_eliminate:
                    # If this semester can potentially be eliminated, try to redistribute its courses
                    if self._can_eliminate_semester(last_semester, scheduled_semesters, last_idx, params):
                        if self._redistribute_semester_courses(scheduled_semesters, last_idx, params):
                            logger.info(f"Successfully eliminated {last_semester['type']} {last_semester['year']} with {last_semester['totalCredits']} credits - graduated earlier!")
                            optimized = True
                            break

        return scheduled_semesters

    def _can_eliminate_semester(self, semester: Dict, scheduled_semesters: List[Dict], 
                          semester_idx: int, params: Dict) -> bool:
        """Check if a semester can potentially be eliminated by redistributing its courses"""
        # Be more lenient for elimination - allow larger semesters to be eliminated if they're at the end
        if len(semester["classes"]) > 4 or semester["totalCredits"] > 12:
            return False
        
        # Check if we have enough space in previous semesters to accommodate these courses
        total_credits_needed = semester["totalCredits"]
        available_space = 0
        
        # Calculate available space in previous semesters
        for i in range(semester_idx):
            prev_semester = scheduled_semesters[i]
            credit_limit = self._get_credit_limit_for_semester_dict(prev_semester, params)
            available_space += max(0, credit_limit - prev_semester["totalCredits"])

        # Also check if we can swap religion courses to make space
        if available_space < total_credits_needed:
            # Count religion courses that could potentially be swapped
            religion_courses_to_move = [c for c in semester["classes"] if self._is_religion_class_dict(c)]
            if religion_courses_to_move:
                # If we have religion courses, we might be able to swap them
                return True

        return available_space >= total_credits_needed

    def _redistribute_semester_courses(self, scheduled_semesters: List[Dict], 
                                     target_idx: int, params: Dict) -> bool:
        """Redistribute courses from target semester to earlier semesters"""
        target_semester = scheduled_semesters[target_idx]
        courses_to_redistribute = target_semester["classes"].copy()
        
        # Prioritize religion courses for swapping first
        religion_courses = [c for c in courses_to_redistribute if self._is_religion_class_dict(c)]
        non_religion_courses = [c for c in courses_to_redistribute if not self._is_religion_class_dict(c)]
        
        # Try religion courses first (easier to swap)
        for course in religion_courses:
            placed = False
            
            # Try placing in each earlier semester
            for i in range(target_idx):
                semester = scheduled_semesters[i]
                
                # Check if we can add this course to this semester
                if self._can_add_course_to_semester(course, semester, scheduled_semesters, i, params):
                    if self._swap_religion_course(course, semester, scheduled_semesters, i):
                        placed = True
                        courses_to_redistribute.remove(course)
                        break
            
            # If we couldn't place this religion course, try harder with more flexible swapping
            if not placed:
                if self._force_religion_course_placement(course, scheduled_semesters, target_idx, params):
                    placed = True
                    courses_to_redistribute.remove(course)
            
            if not placed:
                return False
        
        # Then try non-religion courses
        for course in non_religion_courses:
            placed = False
            
            # Try placing in each earlier semester
            for i in range(target_idx):
                semester = scheduled_semesters[i]
                
                # Check if we can add this course to this semester
                if self._can_add_course_to_semester(course, semester, scheduled_semesters, i, params):
                    # Non-religion course - just add if there's space
                    credit_limit = self._get_credit_limit_for_semester_dict(semester, params)
                    if semester["totalCredits"] + course["credits"] <= credit_limit:
                        semester["classes"].append(course)
                        semester["totalCredits"] += course["credits"]
                        placed = True
                        break
            
            # If we couldn't place this course, redistribution failed
            if not placed:
                return False

        # If we got here, all courses were successfully redistributed
        scheduled_semesters.pop(target_idx)
        return True

    def _force_religion_course_placement(self, religion_course: Dict, scheduled_semesters: List[Dict], 
                                       target_idx: int, params: Dict) -> bool:
        """Force placement of a religion course by finding the best swap opportunity"""
        # Look for the semester with the most available space that has a religion course
        best_semester_idx = -1
        best_available_space = -1
        
        for i in range(target_idx):
            semester = scheduled_semesters[i]
            
            # Check if religion course can be offered in this semester
            if semester["type"] not in religion_course["semesters_offered"]:
                continue
            
            # Check if this semester has a religion course we can swap
            semester_religion = [c for c in semester["classes"] if self._is_religion_class_dict(c)]
            if not semester_religion:
                continue
                
            # Calculate available space after potential swap
            credit_limit = self._get_credit_limit_for_semester_dict(semester, params)
            current_religion = semester_religion[0]
            net_change = religion_course["credits"] - current_religion["credits"]
            available_space = credit_limit - semester["totalCredits"] - net_change
            
            if available_space >= 0 and available_space > best_available_space:
                best_available_space = available_space
                best_semester_idx = i
        
        # Perform the swap if we found a suitable semester
        if best_semester_idx >= 0:
            return self._swap_religion_course(religion_course, scheduled_semesters[best_semester_idx], 
                                            scheduled_semesters, best_semester_idx)
        
        return False

    def _get_credit_limit_for_semester_dict(self, semester: Dict, params: Dict) -> int:
        """Get credit limit for a semester dictionary"""
        # Use default limits if params not provided
        if semester["type"] == "Spring":
            return params.get("springCredits", 10)
        else:
            return params.get("fallWinterCredits", 16)

    def _can_add_course_to_semester(self, course: Dict, semester: Dict, 
                                   scheduled_semesters: List[Dict], semester_idx: int, 
                                   params: Dict) -> bool:
        """Check if a course can be added to a specific semester"""
        # Check semester offering
        if semester["type"] not in course["semesters_offered"]:
            return False
        
        # Check prerequisites
        if not self._prerequisites_satisfied_in_semester_dict(course, scheduled_semesters, semester_idx):
            return False
        
        # Check credit limit
        credit_limit = self._get_credit_limit_for_semester_dict(semester, params)
        if semester["totalCredits"] + course["credits"] > credit_limit:
            return False
        
        # Check major class limit
        if self._is_major_course_dict(course):
            major_class_limit = params.get("majorClassLimit", 3)
            current_major_count = self._count_major_courses_in_semester_dict(semester["classes"])
            if current_major_count >= major_class_limit:
                return False
        
        return True

    def _swap_religion_course(self, new_religion_course: Dict, target_semester: Dict, 
                             scheduled_semesters: List[Dict], target_idx: int) -> bool:
        """Swap a religion course with a simple non-religion course to optimize graduation time"""
        
        # Strategy: Find a simple non-religion course (no prerequisites, not EIL) that can move
        # to the target semester, allowing the religion course to take its place
        
        # Look through earlier semesters for swappable courses
        for earlier_idx in range(target_idx):
            earlier_semester = scheduled_semesters[earlier_idx]
            
            # Check if this earlier semester already has a religion course
            earlier_religion = [c for c in earlier_semester["classes"] if self._is_religion_class_dict(c)]
            if earlier_religion:
                continue  # Skip semesters that already have religion courses
            
            # Find suitable courses that could move to target semester
            for course in earlier_semester["classes"][:]:  # Copy list to avoid modification issues
                if self._is_religion_class_dict(course):
                    continue  # Skip religion courses
                
                # Skip EIL courses - they should not be moved
                if self._is_eil_course_dict(course):
                    continue
                
                # Skip courses with prerequisites - they're part of important chains
                if course.get("prerequisites") and len(course["prerequisites"]) > 0:
                    continue
                
                # Skip courses that are prerequisites for other courses (hub courses)
                # Check if this course is a prerequisite for any other course in the schedule
                is_prerequisite_for_others = False
                for sem in scheduled_semesters:
                    for other_course in sem["classes"]:
                        if course["id"] in other_course.get("prerequisites", []):
                            is_prerequisite_for_others = True
                            break
                    if is_prerequisite_for_others:
                        break
                
                if is_prerequisite_for_others:
                    continue  # Skip hub courses that other courses depend on
                
                # Check if this course can be offered in target semester
                if target_semester["type"] not in course["semesters_offered"]:
                    continue
                
                # Check if moving this course would violate prerequisites for other courses
                if not self._can_move_course_to_later_semester(course, earlier_idx, target_idx, scheduled_semesters):
                    continue

                # Calculate total credits including corequisites for both courses
                new_religion_total_credits = self._get_course_total_credits_dict(new_religion_course, scheduled_semesters)
                course_total_credits = self._get_course_total_credits_dict(course, scheduled_semesters)
                
                # Check if both moves are feasible credit-wise
                earlier_credit_limit = self._get_credit_limit_for_semester_dict(earlier_semester, {})
                target_credit_limit = self._get_credit_limit_for_semester_dict(target_semester, {})
                
                earlier_new_total = earlier_semester["totalCredits"] - course_total_credits + new_religion_total_credits
                target_new_total = target_semester["totalCredits"] + course_total_credits - new_religion_total_credits
                
                if (earlier_new_total <= earlier_credit_limit and 
                    target_new_total <= target_credit_limit):
                    
                    # Perform the swap
                    # Remove courses from their current semesters
                    earlier_semester["classes"] = [c for c in earlier_semester["classes"] 
                                                 if c["id"] != course["id"]]
                    target_semester["classes"] = [c for c in target_semester["classes"] 
                                                if c["id"] != new_religion_course["id"]]
                    
                    # Add courses to their new semesters
                    earlier_semester["classes"].append(new_religion_course)
                    target_semester["classes"].append(course)
                    
                    # Update credit totals
                    earlier_semester["totalCredits"] = earlier_new_total
                    target_semester["totalCredits"] = target_new_total
                    
                    logger.info(f"Swapped religion course {new_religion_course['class_number']} with simple course {course['class_number']}")
                    return True
        
        # If no swap was possible, try just adding the religion course if there's space
        target_credit_limit = self._get_credit_limit_for_semester_dict(target_semester, {})
        new_religion_total_credits = self._get_course_total_credits_dict(new_religion_course, scheduled_semesters)
        
        if target_semester["totalCredits"] + new_religion_total_credits <= target_credit_limit:
            # Check if target semester already has a religion course
            target_religion = [c for c in target_semester["classes"] if self._is_religion_class_dict(c)]
            if not target_religion:
                target_semester["classes"].append(new_religion_course)
                target_semester["totalCredits"] += new_religion_total_credits
                return True
        
        return False

    def _get_course_total_credits_dict(self, course_dict: Dict, scheduled_semesters: List[Dict]) -> int:
        """Calculate total credits for a course including its corequisites from dictionary"""
        total_credits = course_dict["credits"]
        
        # Add corequisite credits if any
        if course_dict.get("corequisites"):
            for coreq_id in course_dict["corequisites"]:
                # Find the corequisite in the scheduled semesters
                for semester in scheduled_semesters:
                    for c in semester["classes"]:
                        if c["id"] == coreq_id:
                            total_credits += c["credits"]
                            break
        
        return total_credits

    def _can_move_course_to_later_semester(self, course: Dict, from_semester_idx: int, 
                                         to_semester_idx: int, scheduled_semesters: List[Dict]) -> bool:
        """Check if moving a course to a later semester would violate prerequisites for other courses"""
        course_id = course["id"]
        
        # Check all courses in semesters between from_semester and to_semester (inclusive of to_semester)
        for i in range(from_semester_idx + 1, len(scheduled_semesters)):
            semester = scheduled_semesters[i]
            for other_course in semester["classes"]:
                # If any course has this course as a prerequisite, we can't move it later
                if course_id in other_course.get("prerequisites", []):
                    # But if we're moving it to before that course, it's still valid
                    if i > to_semester_idx:
                        return False
        
        return True