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
    course_type: str = ""
    course_id: str = ""
    is_elective_section: bool = False

@dataclass
class Semester:
    type: str  # Fall, Winter, Spring
    year: int
    credit_limit: int
    target_credits: int = 0  # Target credits for this semester
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
            
        message = str(record.msg)
        
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

class SemesterBasedOptimizer:
    def __init__(self):
        self.satisfied_sections: Set[int] = set()
        
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
                course_id=str(data.get("course_id", "")),
                is_elective_section=data.get("is_elective_section", False)
            )
            courses.append(course)
        return courses

    def _sort_by_prerequisites(self, courses: List[Course]) -> List[Course]:
        """Sort courses optimizing for balanced distribution while respecting dependencies"""
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
            chain_depths[course.id] = get_chain_depth(course.id)
            prereq_chains[course.id] = get_all_prerequisites(course.id)
            dependent_courses[course.id] = 0
        
        # Count dependencies in a second pass
        for course in courses:
            for prereq_id in prereq_chains[course.id]:
                dependent_courses[prereq_id] = dependent_courses.get(prereq_id, 0) + 1
    
        # Calculate semester flexibility (fewer offerings = less flexible)
        offering_flexibility = {c.id: len(c.semesters_offered) for c in courses}
        
        # Sort courses based on multiple criteria for balanced distribution
        return sorted(courses, key=lambda c: (
            # Religion courses get highest priority for even distribution
            0 if self._is_religion_class(c) else 1,
            -chain_depths[c.id],            # Deep prerequisite chains first
            -dependent_courses[c.id],       # Courses that unlock more dependencies
            offering_flexibility[c.id],     # Less flexible courses scheduled earlier
            c.id                            # Stable sort
        ))

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

    def _is_major_course(self, course: Course) -> bool:
        """Check if a course is a major course"""
        return course.course_type == "major"

    def _count_major_courses_in_semester(self, semester_courses: List[Course]) -> int:
        """Count the number of major courses in a semester"""
        return sum(1 for course in semester_courses if self._is_major_course(course))

    def _calculate_target_credits_per_semester(self, all_courses: List[Course], 
                                             target_semesters: int, 
                                             first_year_limits: Dict,
                                             limit_first_year: bool) -> List[int]:
        """Calculate target credits to efficiently use all target semesters with dynamic credit allocation"""
        total_credits = sum(course.credits for course in all_courses)
        target_credits = []
        
        if limit_first_year and first_year_limits and target_semesters >= 3:
            # First year with limits - use the actual specified limits
            first_year_targets = [
                first_year_limits.get("fallWinterCredits", 12),  # Winter 2025
                first_year_limits.get("springCredits", 9),       # Spring 2025  
                first_year_limits.get("fallWinterCredits", 12)   # Fall 2025
            ]
            target_credits.extend(first_year_targets)
            
            # Calculate remaining credits after first year
            first_year_total = sum(first_year_targets)
            remaining_credits = total_credits - first_year_total
            remaining_semesters = target_semesters - 3
            
            if remaining_semesters > 0:
                # Distribute remaining credits to use maximum capacity efficiently
                avg_credits = remaining_credits / remaining_semesters
                
                for i in range(remaining_semesters):
                    # Use higher targets to pack efficiently within target semesters
                    if i < remaining_semesters - 1:
                        # Use near-maximum capacity for efficient packing
                        sem_target = min(18, max(12, int(avg_credits) + 2))  # Aim for higher capacity
                    else:
                        # Final semester gets whatever remains
                        allocated_so_far = sum(target_credits[3:])
                        sem_target = remaining_credits - allocated_so_far
                        sem_target = max(3, min(sem_target, 18))  # Allow light final semester
                    
                    target_credits.append(sem_target)
        else:
            # No first year limits - distribute to efficiently use target semesters
            avg_credits = total_credits / target_semesters
            
            for i in range(target_semesters):
                if i < target_semesters - 1:
                    # Use efficient packing - aim for substantial credit loads
                    sem_target = min(18, max(12, int(avg_credits) + 1))
                else:
                    # Final semester gets remaining credits
                    allocated_so_far = sum(target_credits)
                    sem_target = total_credits - allocated_so_far
                    sem_target = max(3, min(sem_target, 18))
                
                target_credits.append(sem_target)

        logger.info(f"Efficient target credits to use exactly {target_semesters} semesters: {target_credits}")
        logger.info(f"Total target credits: {sum(target_credits)}, Actual total: {total_credits}")
        return target_credits

    def _find_best_semester_for_course(self, course: Course, available_semesters: List[Semester],
                                     all_scheduled_courses: List[Course], 
                                     scheduled_semesters: List[Dict],
                                     current_semester_idx: int,
                                     target_semesters: int) -> int:
        """Find the best semester to schedule a course with strong preference for spreading across target semesters"""
        best_semester_idx = -1
        best_score = -1
        
        # Look ahead through target semesters (and a bit beyond for flexibility)
        max_look_ahead = min(len(available_semesters), target_semesters + 3)
        
        for i in range(current_semester_idx, max_look_ahead):
            semester = available_semesters[i]
            
            # Check basic constraints
            if semester.type not in course.semesters_offered:
                continue
                
            if not self._prerequisites_satisfied_before_semester(
                course, all_scheduled_courses, i, scheduled_semesters):
                continue
            
            # Check if adding course would exceed credit limit
            course_credits = self._get_total_credits(course, [course])
            if semester.total_credits + course_credits > semester.credit_limit:
                continue
            
            # Check religion course limitation
            if self._is_religion_class(course):
                religion_in_semester = sum(1 for c in semester.classes if self._is_religion_class(c))
                if religion_in_semester >= 1:
                    continue
            
            # Calculate score with strong emphasis on using target semesters
            after_credits = semester.total_credits + course_credits
            
            # Primary scoring: Heavy penalty for going beyond target semesters early
            if i >= target_semesters:
                # Heavily penalize scheduling beyond target unless absolutely necessary
                base_score = -100 + (target_semesters * 2 - i)  # Decreasing penalty the further out
            else:
                # Within target range - encourage later scheduling to spread out
                base_score = 100
                
                # Bonus for scheduling later within target range (spread courses out)
                spread_bonus = i * 2  # Prefer later semesters within target
                base_score += spread_bonus
            
            # Secondary: How close to target credits (but less important than spreading)
            distance_from_target = abs(semester.target_credits - after_credits)
            target_score = max(0, 10 - distance_from_target)
            
            # Tertiary: Prefer semesters that are under-filled
            if after_credits <= semester.target_credits:
                under_target_bonus = 5
            else:
                under_target_bonus = -2  # Small penalty for exceeding target
            
            # Quaternary: Course type considerations
            type_bonus = 0
            if self._is_religion_class(course):
                # Religion courses should be distributed throughout
                type_bonus = 3
            elif self._is_major_course(course):
                # Major courses can be scheduled more flexibly
                type_bonus = 1
            
            total_score = base_score + target_score + under_target_bonus + type_bonus
            
            if total_score > best_score:
                best_score = total_score
                best_semester_idx = i
        
        return best_semester_idx

    def create_schedule(self, processed_data: Dict) -> Dict:
        """Create a schedule that uses exactly the target number of semesters"""
        try:
            # Validate input (same as constraint optimizer)
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
                
            logger.info(f"Starting semester-based schedule creation with {len(processed_data['classes'])} classes")
            
            # Initialize tracking sets (same as constraint optimizer)
            self.satisfied_sections = set()
            scheduled_course_ids = set()
            
            params = processed_data["parameters"]
            target_semesters = params.get("targetSemesters")
            
            if not target_semesters:
                raise ValueError("Target semesters not specified for semester-based scheduling")
            
            self._all_courses = self._convert_to_courses(processed_data["classes"])
            
            # Set up first year limits (same as constraint optimizer)
            if not params.get("firstYearLimits") or not isinstance(params["firstYearLimits"], dict):
                params["firstYearLimits"] = {
                    "fallWinterCredits": 18,
                    "springCredits": 12
                }
            
            # Group courses by section and process electives (same as constraint optimizer)
            sections = self._group_by_section(self._all_courses)
            courses_to_schedule = []
            
            # Process each section (identical to constraint optimizer)
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
                                logger.info(f"Selected electives for section {section_id}: {[c.class_number for c in combination]}")
                        except ValueError as e:
                            logger.error(f"Failed to satisfy section {section_id}: {str(e)}")
                            return {
                                "error": str(e),
                                "metadata": {
                                    "approach": "semesters-based",
                                    "startSemester": params["startSemester"],
                                    "success": False
                                }
                            }
                else:
                    required_courses = [c for c in courses if not c.is_elective]
                    courses_to_schedule.extend(required_courses)

            # Calculate target credits per semester for distribution
            target_credits = self._calculate_target_credits_per_semester(
                courses_to_schedule, 
                target_semesters,
                params["firstYearLimits"],
                params.get("limitFirstYear", False)
            )
            
            logger.info(f"Target credits per semester: {target_credits}")
            
            # Initialize semesters with target distribution
            semesters = self._initialize_semesters_for_target(
                params["startSemester"],
                target_semesters,
                target_credits,
                params
            )
            
            # Split courses into EIL and regular courses (same as constraint optimizer)
            eil_courses = [c for c in courses_to_schedule if self._is_eil_course(c)]
            regular_courses = [c for c in courses_to_schedule if not self._is_eil_course(c)]
            
            # Group EIL courses according to scheduling rules (same as constraint optimizer)
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
            
            # Sort regular courses by prerequisites (same logic, adapted for distribution)
            sorted_regular_courses = self._sort_by_prerequisites(regular_courses)
            
            # Main scheduling loop - using constraint optimizer logic with distribution adaptations
            current_semester_idx = 0
            scheduled_semesters = []
            remaining_courses = sorted_regular_courses.copy()
            all_scheduled_courses = []
            
            while remaining_courses or first_sem_required or first_sem_flexible or second_sem_required:
                # Create new semester if needed (same as constraint optimizer)
                if current_semester_idx >= len(semesters):
                    last_sem = semesters[-1]
                    new_sem = self._create_next_semester(last_sem, params)
                    semesters.append(new_sem)
                    
                semester = semesters[current_semester_idx]
                semester_courses = []
                current_credits = 0
                courses_scheduled_this_semester = False
                
                # FIRST PRIORITY: Handle EIL courses based on semester index (same as before)
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
            
                # SECOND PRIORITY: Schedule regular courses with efficient packing
                course_priorities = []

                for course in remaining_courses:
                    # Skip if already scheduled
                    if course.id in scheduled_course_ids:
                        continue
                        
                    # Check if course can be offered this semester
                    if semester.type not in course.semesters_offered:
                        continue
                        
                    # Check prerequisites are satisfied
                    if not self._prerequisites_satisfied_before_semester(course, all_scheduled_courses, 
                                                                     current_semester_idx, scheduled_semesters):
                        continue

                    # Check religion class limitation
                    if self._is_religion_class(course):
                        religion_courses_in_semester = sum(1 for c in semester_courses if self._is_religion_class(c))
                        if religion_courses_in_semester >= 1:
                            continue
                        
                        added_courses_preview = self._add_course_with_coreqs(course, remaining_courses)
                        religion_in_coreqs = sum(1 for c in added_courses_preview if self._is_religion_class(c))
                        if religion_in_coreqs > 1:
                            continue

                    # Calculate priority for efficient packing within target semesters
                    priority = 0

                    # 1. Highest priority for prerequisite unlocking
                    unlocks_count = sum(1 for c in remaining_courses if course.id in c.prerequisites)
                    priority += unlocks_count * 25

                    # 2. Foundation courses priority
                    if not course.prerequisites:
                        priority += 40 if unlocks_count > 0 else 8

                    # 3. Prerequisite chain priority
                    chain_length = len([c for c in all_scheduled_courses if c.id in course.prerequisites])
                    priority += chain_length * 8

                    # 4. Limited offering priority
                    flexibility_penalty = (3 - min(len(course.semesters_offered), 3)) * 12
                    priority += flexibility_penalty

                    # 5. Religion course distribution
                    if self._is_religion_class(course):
                        priority += 18
                    
                    # 6. Major/core course priority
                    if course.course_type in ["major", "core"]:
                        priority += 5
                    
                    # 7. CRITICAL: Urgency bonus for later semesters to pack efficiently
                    if current_semester_idx >= target_semesters * 0.7:  # In later 30% of target semesters
                        urgency_bonus = (current_semester_idx - target_semesters * 0.7) * 15
                        priority += urgency_bonus
                    
                    # 8. Efficiency bonus - prefer courses that help reach target credits
                    course_credits = self._get_total_credits(course, remaining_courses)
                    after_credits = current_credits + course_credits
                    
                    # Bonus for getting closer to target without exceeding credit limit
                    if after_credits <= semester.credit_limit:
                        if after_credits >= semester.target_credits * 0.8:  # Close to target
                            priority += 8
                        if semester.target_credits <= after_credits <= semester.credit_limit:
                            priority += 5  # Within good range
                    
                    course_priorities.append((course, priority))

                # Sort by priority
                course_priorities.sort(key=lambda x: x[1], reverse=True)

                # Schedule as many as fit within credit limits
                for course, _ in course_priorities:
                    # Check if there's space for the course and its corequisites
                    course_credits = self._get_total_credits(course, remaining_courses)
                    if current_credits + course_credits <= semester.credit_limit:
                        
                        try:
                            # Add course and its corequisites
                            added_courses = self._add_course_with_coreqs(course, remaining_courses)
                            
                            # Religion course validation
                            if self._is_religion_class(course):
                                existing_religion = sum(1 for c in semester_courses if self._is_religion_class(c))
                                new_religion = sum(1 for c in added_courses if self._is_religion_class(c))
                                
                                if existing_religion + new_religion > 1:
                                    continue
                            
                            semester_courses.extend(added_courses)
                            current_credits += course_credits
                            courses_scheduled_this_semester = True
                            
                            all_scheduled_courses.extend(added_courses)
                            
                            # Remove scheduled courses
                            for c in added_courses:
                                if c in remaining_courses:
                                    remaining_courses.remove(c)
                                    scheduled_course_ids.add(c.id)
                                    
                            logger.info(f"Scheduled {course.class_number} in {semester.type} {semester.year} "
                                      f"(semester {current_semester_idx + 1}/{target_semesters}, "
                                      f"credits: {current_credits}/{semester.credit_limit})")
                            
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
                    logger.info(f"Completed {semester.type} {semester.year} with {current_credits} credits "
                              f"(target: {semester.target_credits})")
                
                # Move to next semester
                current_semester_idx += 1
                
                # Break if all courses scheduled
                if not (remaining_courses or first_sem_required or first_sem_flexible or second_sem_required):
                    break

            # Handle any remaining courses if we're at semester limit
            if (remaining_courses or first_sem_required or first_sem_flexible or second_sem_required) and current_semester_idx >= target_semesters:
                logger.warning(f"Some courses remain unscheduled at target semester limit. Creating additional semesters.")
                
                while remaining_courses or first_sem_required or first_sem_flexible or second_sem_required:
                    if current_semester_idx >= len(semesters):
                        last_sem = semesters[-1]
                        new_sem = self._create_next_semester(last_sem, params)
                        semesters.append(new_sem)
                    
                    semester = semesters[current_semester_idx]
                    semester_courses = []
                    current_credits = 0
                    
                    # Schedule remaining courses in overflow semesters
                    for course in remaining_courses[:]:
                        if semester.type in course.semesters_offered:
                            course_credits = self._get_total_credits(course, remaining_courses)
                            if current_credits + course_credits <= semester.credit_limit:
                                try:
                                    added_courses = self._add_course_with_coreqs(course, remaining_courses)
                                    semester_courses.extend(added_courses)
                                    current_credits += course_credits
                                    
                                    for c in added_courses:
                                        if c in remaining_courses:
                                            remaining_courses.remove(c)
                                            scheduled_course_ids.add(c.id)
                                            all_scheduled_courses.append(c)
                                except Exception as e:
                                    logger.error(f"Error scheduling overflow course {course.class_number}: {str(e)}")
                                    continue
                    
                    # Handle remaining EIL courses
                    for eil_list in [first_sem_required, first_sem_flexible, second_sem_required]:
                        for course in eil_list[:]:
                            if semester.type in course.semesters_offered:
                                if current_credits + course.credits <= semester.credit_limit:
                                    semester_courses.append(course)
                                    current_credits += course.credits
                                    scheduled_course_ids.add(course.id)
                                    eil_list.remove(course)
                                    all_scheduled_courses.append(course)
                    
                    if semester_courses:
                        scheduled_semesters.append({
                            "type": semester.type,
                            "year": semester.year,
                            "classes": [self._course_to_dict(c) for c in semester_courses],
                            "totalCredits": current_credits
                        })
                    
                    current_semester_idx += 1
                    
                    # Break if all courses scheduled
                    if not (remaining_courses or first_sem_required or first_sem_flexible or second_sem_required):
                        break
                        
                    # Safety break to prevent infinite loop
                    if current_semester_idx >= target_semesters + 10:
                        logger.error("Too many overflow semesters created, stopping")
                        break

            # Log the final result
            actual_semesters = len(scheduled_semesters)
            logger.info(f"Created schedule with {actual_semesters} semesters (target: {target_semesters})")
            
            # NEW CODE: Check if we need to spread the schedule
            if actual_semesters < target_semesters:
                logger.info(f"Schedule finished efficiently in {actual_semesters} semesters (target: {target_semesters})")
                logger.info(f"Spreading schedule to use exactly {target_semesters} semesters")
                
                # Spread the schedule to fill target_semesters
                spread_semesters = self._spread_schedule_to_target_semesters(
                    scheduled_semesters, 
                    target_semesters,
                    params["startSemester"]
                )
                
                # Replace with the spread schedule
                scheduled_semesters = spread_semesters
                actual_semesters = len(scheduled_semesters)
                
                logger.info(f"Successfully spread schedule across {actual_semesters} semesters")
            
            # Success if within target or only slightly over due to constraints
            met_target = actual_semesters <= target_semesters
            
            return {
                "metadata": {
                    "approach": "semesters-based",
                    "startSemester": params["startSemester"],
                    "targetSemesters": target_semesters,
                    "actualSemesters": actual_semesters,
                    "distributed": met_target,
                    "success": True,
                    "improvements": [
                        f"Efficiently packed courses into {actual_semesters} semesters",
                        f"Target was {target_semesters} semesters",
                        f"Target {'achieved' if met_target else f'exceeded by {actual_semesters - target_semesters}'}",
                        "Dynamically used credit limits to fit within target",
                        "Maintained all course scheduling rules and constraints"
                    ]
                },
                "schedule": scheduled_semesters
            }
        
        except Exception as e:
            logger.error(f"Error in semester-based schedule creation: {str(e)}")
            return {
                "error": f"Semester-based schedule creation failed: {str(e)}",
                "metadata": {
                    "approach": "semesters-based",
                    "startSemester": params.get("startSemester", "Unknown"),
                    "success": False
                }
            }
    
    # All helper methods copied from constraint optimizer
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
        
        elective_courses = [c for c in courses if c.is_elective]
        
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
    
        section_id = courses[0].section_id
        if section_id in self.satisfied_sections:
            logger.info(f"Section {section_id} already satisfied")
            return []
            
        best_combination = None
        best_total = 0
        
        for size in range(1, len(elective_courses) + 1):
            current_combo = []
            current_total = 0
            
            for course in elective_courses[:size]:
                course_and_coreqs = self._get_course_with_coreqs(course, self._all_courses)
                current_combo.extend(course_and_coreqs)
                current_total = sum(c.credits for c in current_combo)
                
                if current_total >= credits_needed:
                    best_combination = current_combo
                    best_total = current_total
                    break
                
        if best_combination:
            self.satisfied_sections.add(section_id)
            logger.info(f"Found combination for section {section_id}: {[c.class_number for c in best_combination]} = {best_total} cr "
                       f"(needed {credits_needed})")
            return best_combination

        logger.warning(f"Could not meet credit requirement for section {section_id}: needed {credits_needed} credits")
        return []

    def _get_course_with_coreqs(self, course: Course, available_courses: List[Course]) -> List[Course]:
        """Get a course and all its corequisites"""
        result = [course]
        
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
            
        # Set credit limits to maximum for semester-based approach
        if new_type == "Spring":
            credit_limit = 12
        else:
            credit_limit = 18
            
        target_credit = credit_limit // 2  # Default target
        return Semester(new_type, new_year, credit_limit, target_credit)

    def _get_total_credits(self, course: Course, available_courses: List[Course]) -> int:
        """Calculate total credits including all corequisites"""
        total = course.credits
        processed = {course.id}
        to_check = [course]
        
        while to_check:
            current = to_check.pop()
            for coreq_id in current.corequisites:
                if coreq_id in processed:
                    continue
                    
                coreq = next((c for c in available_courses if c.id == coreq_id), None)
                if coreq:
                    processed.add(coreq_id)
                    total += coreq.credits
                    to_check.append(coreq)
        
        return total

    def _add_course_with_coreqs(self, course: Course, remaining_courses: List[Course]) -> List[Course]:
        """Add a course and its corequisites"""
        added = [course]
        required_coreqs = set()
        to_check = [course]
        
        while to_check:
            current = to_check.pop()
            for coreq_id in current.corequisites:
                if isinstance(coreq_id, dict):
                    coreq_id = coreq['id']
                
                if coreq_id in required_coreqs:
                    continue
                
                coreq = next((c for c in remaining_courses if c.id == coreq_id), None)
                
                if not coreq:
                    coreq = next((c for c in self._all_courses if c.id == coreq_id), None)
                
                if coreq:
                    required_coreqs.add(coreq_id)
                    to_check.append(coreq)
                    
                    if coreq.course_type == "system" and course.course_type != "system":
                        logger.info(f"Updating {coreq.class_number} type from system to {course.course_type}")
                        coreq.course_type = course.course_type
    
        for coreq_id in required_coreqs:
            coreq = (next((c for c in remaining_courses if c.id == coreq_id), None) or 
                    next((c for c in self._all_courses if c.id == coreq_id), None))
            if coreq and coreq not in added:
                added.append(coreq)
                logger.info(f"Adding corequisite {coreq.class_number} with {course.class_number}")
    
        return added

    def _prerequisites_satisfied_before_semester(self, course: Course, all_scheduled_courses: List[Course], 
                                          current_semester_idx: int, scheduled_semesters: List[Dict]) -> bool:
        """Check if prerequisites are satisfied in previous semesters"""
        if self._is_eil_course(course):
            return True
            
        if not course.prerequisites:
            return True
            
        courses_in_previous_semesters = []
        for i in range(current_semester_idx):
            if i < len(scheduled_semesters):
                semester = scheduled_semesters[i]
                for course_dict in semester["classes"]:
                    courses_in_previous_semesters.append(course_dict["id"])

        return all(prereq_id in courses_in_previous_semesters for prereq_id in course.prerequisites)

    def _initialize_semesters_for_target(self, start_semester: str, target_semesters: int,
                                       target_credits: List[int], params: Dict) -> List[Semester]:
        """Initialize semesters with target credit distribution"""
        sem_type, year = start_semester.split()
        year = int(year)
        
        semesters = []
        for i in range(target_semesters + 5):  # Add extra buffer semesters
            # Set credit limits (always max for semester-based)
            if sem_type == "Spring":
                credit_limit = 12
            else:
                credit_limit = 18
            
            # Apply first year limits if specified
            if i < 3 and params.get("limitFirstYear"):
                if sem_type == "Spring":
                    credit_limit = params["firstYearLimits"]["springCredits"]
                else:
                    credit_limit = params["firstYearLimits"]["fallWinterCredits"]
            
            # Set target credits for balanced distribution
            target_credit = target_credits[i] if i < len(target_credits) else (credit_limit // 2)
            
            semester = Semester(sem_type, year, credit_limit, target_credit)
            semesters.append(semester)
            
            # Update semester type and year
            if sem_type == "Fall":
                sem_type = "Winter"
                year += 1
            elif sem_type == "Winter":
                sem_type = "Spring"
            else:  # Spring
                sem_type = "Fall"
                
        return semesters

    def _should_force_religion_scheduling(self, remaining_courses: List[Course], 
                                        scheduled_semesters: List[Dict]) -> bool:
        """Check if we should force religion course scheduling to avoid end-stacking"""
        religion_courses_left = sum(1 for c in remaining_courses if self._is_religion_class(c))
        
        # If we have no religion courses left, don't force
        if religion_courses_left == 0:
            return False
        
        # Force religion scheduling immediately if we have any religion courses left
        if religion_courses_left > 0:
            return True
            
        return False

    def _extract_courses_from_schedule(self, schedule: List[Dict]) -> List[Dict]:
        """Extract all courses from the schedule"""
        all_courses = []
        for semester in schedule:
            all_courses.extend(semester["classes"])
        return all_courses

    def _spread_schedule_to_target_semesters(self, original_semesters: List[Dict], 
                                   target_semesters: int,
                                   start_semester: str) -> List[Dict]:
        """Spread the schedule to fill exactly the target number of semesters"""
        if len(original_semesters) >= target_semesters:
            return original_semesters
        
        # 1. Generate empty semesters up to the target
        spread_semesters = self._create_empty_semesters(start_semester, target_semesters)
        
        # 2. Identify prerequisite chains in the original schedule
        course_chains = self._identify_chains_in_schedule(original_semesters)
        logger.info(f"Found {len(course_chains)} prerequisite chains to preserve while spreading")
        
        # 3. Extract all courses from original schedule grouped by type
        all_scheduled_courses = self._extract_courses_from_schedule(original_semesters)
        religion_courses = [c for c in all_scheduled_courses if c.get("course_type") == "religion"]
        major_courses = [c for c in all_scheduled_courses if c.get("course_type") == "major"]
        minor_courses = [c for c in all_scheduled_courses if c.get("course_type") == "minor"]
        other_courses = [c for c in all_scheduled_courses 
                       if c.get("course_type") not in ["religion", "major", "minor"]]
        
        logger.info(f"Extracting courses to spread: {len(religion_courses)} religion, "
                   f"{len(major_courses)} major, {len(minor_courses)} minor, "
                   f"{len(other_courses)} other")
        
        # 4. Calculate the ideal distribution per semester
        spread_factor = target_semesters / len(original_semesters)
        
        # 5. Sort chains by length and complexity for better spreading
        sorted_chains = sorted(course_chains, key=len, reverse=True)
        
        # 6. First place chains while maintaining prerequisites
        self._place_chains_in_spread_schedule(sorted_chains, spread_semesters, spread_factor)
        
        # 7. Track which courses have been placed from chains
        placed_course_ids = set()
        for semester in spread_semesters:
            for course in semester["classes"]:
                placed_course_ids.add(course["id"])
    
        # 8. Filter out courses already placed in chains
        religion_courses = [c for c in religion_courses if c["id"] not in placed_course_ids]
        major_courses = [c for c in major_courses if c["id"] not in placed_course_ids]
        minor_courses = [c for c in minor_courses if c["id"] not in placed_course_ids]
        other_courses = [c for c in other_courses if c["id"] not in placed_course_ids]
        
        # 9. Place remaining courses with balanced distribution
        self._distribute_courses_evenly(
            religion_courses, major_courses, minor_courses, other_courses,
            spread_semesters
        )
        
        # 10. Update total credits for each semester
        for semester in spread_semesters:
            semester["totalCredits"] = sum(c["credits"] for c in semester["classes"])
    
        return spread_semesters

    def _create_empty_semesters(self, start_semester: str, target_semesters: int) -> List[Dict]:
        """Create empty semesters up to the target count"""
        sem_type, year = start_semester.split()
        year = int(year)
        
        semesters = []
        for i in range(target_semesters):
            # Set credit limits
            if sem_type == "Spring":
                credit_limit = 12
            else:
                credit_limit = 18
            
            semester = {
                "type": sem_type,
                "year": year,
                "classes": [],
                "totalCredits": 0,
                "creditLimit": credit_limit
            }
            semesters.append(semester)
            
            # Update for next semester
            if sem_type == "Fall":
                sem_type = "Winter"
                year += 1
            elif sem_type == "Winter":
                sem_type = "Spring"
            else:  # Spring
                sem_type = "Fall"
    
        return semesters

    def _identify_chains_in_schedule(self, schedule: List[Dict]) -> List[List[Dict]]:
        """Identify prerequisite chains in the scheduled courses"""
        # Extract all courses from the schedule
        all_courses = []
        for semester in schedule:
            all_courses.extend(semester["classes"])
    
        # Create a map of course IDs to courses
        course_map = {course["id"]: course for course in all_courses}
    
        # Find root courses (no prerequisites or prerequisites not in our schedule)
        scheduled_ids = set(course_map.keys())
        root_courses = []
    
        for course in all_courses:
            prereqs = course.get("prerequisites", [])
            if not prereqs or not any(prereq_id in scheduled_ids for prereq_id in prereqs):
                root_courses.append(course)
    
        # Identify chains starting from root courses
        chains = []
        visited = set()
    
        for root in root_courses:
            if root["id"] in visited:
                continue
                
            # Find all courses that depend on this course
            chain = [root]
            visited.add(root["id"])
            
            # Build chain by following prerequisites
            self._build_chain(root, chain, all_courses, course_map, visited)
            
            # Only add chains with more than one course
            if len(chain) > 1:
                chains.append(chain)
        
        return chains

    def _build_chain(self, current_course: Dict, chain: List[Dict], 
                   all_courses: List[Dict], course_map: Dict[int, Dict], 
                   visited: Set[int]) -> None:
        """Recursively build a prerequisite chain"""
        # Find all courses that have current_course as a prerequisite
        for course in all_courses:
            if course["id"] in visited:
                continue
                
            prereqs = course.get("prerequisites", [])
            if current_course["id"] in prereqs:
                chain.append(course)
                visited.add(course["id"])
                self._build_chain(course, chain, all_courses, course_map, visited)

    def _place_chains_in_spread_schedule(self, chains: List[List[Dict]], 
                                       spread_semesters: List[Dict],
                                       spread_factor: float) -> None:
        """Place prerequisite chains in the spread schedule"""
        total_semesters = len(spread_semesters)
        
        # Calculate appropriate spacing between chain elements
        for chain in chains:
            # Determine ideal spacing based on chain length and spread factor
            chain_length = len(chain)
            
            if chain_length == 1:
                # Single course - place anywhere with appropriate balance
                course = chain[0]
                best_semester_idx = self._find_best_semester_for_standalone(
                    course, spread_semesters)
                
                if best_semester_idx >= 0:
                    spread_semesters[best_semester_idx]["classes"].append(course)
                
            else:
                # Apply appropriate spacing for chains
                ideal_spacing = max(1, int(spread_factor))
                
                # Find start position that allows the chain to fit
                max_start = total_semesters - chain_length * ideal_spacing
                start_idx = min(max(0, int(total_semesters * 0.2)), max_start)
                
                # Place chain with spacing
                for i, course in enumerate(chain):
                    # Calculate position with spacing
                    position = start_idx + (i * ideal_spacing)
                    
                    # Ensure we don't exceed available semesters
                    if position < total_semesters:
                        # Check semester type constraints
                        sem_idx = position
                        while sem_idx < total_semesters:
                            sem_type = spread_semesters[sem_idx]["type"]
                            if sem_type in course.get("semesters_offered", []):
                                break
                            sem_idx += 1
                        
                        # If we found a valid semester, place the course
                        if sem_idx < total_semesters:
                            spread_semesters[sem_idx]["classes"].append(course)
                            logger.info(f"Placed chain course {course['class_number']} in semester {sem_idx+1}")
                            # Avoid placing too many in the same semester
                            break
                        
    def _distribute_courses_evenly(self, religion_courses: List[Dict], 
                             major_courses: List[Dict],
                             minor_courses: List[Dict],
                             other_courses: List[Dict],
                             spread_semesters: List[Dict]) -> None:
        """Distribute standalone courses evenly across semesters"""
        # Try to place one religion course per semester if possible
        self._distribute_religion_courses(religion_courses, spread_semesters)
        
        # Distribute major courses with balance
        self._distribute_course_type(major_courses, spread_semesters, 'major')
        
        # Distribute minor courses with balance
        self._distribute_course_type(minor_courses, spread_semesters, 'minor')
        
        # Distribute remaining courses
        self._distribute_course_type(other_courses, spread_semesters, 'other')

    def _distribute_religion_courses(self, religion_courses: List[Dict], 
                              spread_semesters: List[Dict]) -> None:
        """Try to distribute one religion course per semester"""
        remaining_courses = religion_courses.copy()
        
        # First pass - try to place one religion course per semester
        for semester_idx, semester in enumerate(spread_semesters):
            # Skip if semester already has a religion course
            if any(c.get("course_type") == "religion" for c in semester["classes"]):
                continue
            
            # Find a religion course that can be placed in this semester
            for course_idx, course in enumerate(remaining_courses):
                if semester["type"] in course.get("semesters_offered", []):
                    # Check if prerequisites are satisfied
                    if self._prerequisites_satisfied_before_semester_dict(course, 
                                                                      spread_semesters, 
                                                                      semester_idx):
                        # Check credit limit
                        course_credits = course.get("credits", 0)
                        if semester.get("totalCredits", 0) + course_credits <= semester.get("creditLimit", 18):
                            semester["classes"].append(course)
                            semester["totalCredits"] = semester.get("totalCredits", 0) + course_credits
                            logger.info(f"Placed religion course {course['class_number']} in semester {semester_idx+1}")
                            remaining_courses.pop(course_idx)
                            break

        # Second pass - place any remaining religion courses in best available semesters
        for course in remaining_courses:
            best_idx = self._find_best_semester_for_standalone(course, spread_semesters)
            if best_idx >= 0:
                spread_semesters[best_idx]["classes"].append(course)
                spread_semesters[best_idx]["totalCredits"] = spread_semesters[best_idx].get("totalCredits", 0) + course.get("credits", 0)
                logger.info(f"Placed remaining religion course {course['class_number']} in semester {best_idx+1}")

    def _distribute_course_type(self, courses: List[Dict], 
                         spread_semesters: List[Dict],
                         course_type: str) -> None:
        """Distribute courses of a specific type evenly across semesters"""
        remaining_courses = courses.copy()
        
        # Calculate ideal distribution
        if not courses:
            return
            
        courses_per_semester = max(1, len(courses) / len(spread_semesters))
        logger.info(f"Ideal distribution: {courses_per_semester:.2f} {course_type} courses per semester")
        
        # Count existing courses of this type in each semester
        type_counts = []
        for semester in spread_semesters:
            count = sum(1 for c in semester["classes"] if c.get("course_type") == course_type)
            type_counts.append(count)
        
        # Try to distribute evenly
        while remaining_courses:
            # Find semester with fewest courses of this type
            min_count = min(type_counts)
            semester_idx = type_counts.index(min_count)
            
            # Try to place a course in this semester
            placed = False
            for course_idx, course in enumerate(remaining_courses):
                semester = spread_semesters[semester_idx]
                
                # Check if course can be placed in this semester
                if semester["type"] in course.get("semesters_offered", []):
                    # Check prerequisites
                    if self._prerequisites_satisfied_before_semester_dict(course, 
                                                                       spread_semesters, 
                                                                       semester_idx):
                        # Check credit limit
                        course_credits = course.get("credits", 0)
                        if semester.get("totalCredits", 0) + course_credits <= semester.get("creditLimit", 18):
                            semester["classes"].append(course)
                            semester["totalCredits"] = semester.get("totalCredits", 0) + course_credits
                            logger.info(f"Placed {course_type} course {course['class_number']} in semester {semester_idx+1}")
                            remaining_courses.pop(course_idx)
                            type_counts[semester_idx] += 1
                            placed = True
                            break
            
            # If we couldn't place a course in the current semester, try the next one
            if not placed:
                # Mark this semester as full for this course type
                type_counts[semester_idx] = max(type_counts) + 1
                
                # If we've tried all semesters, use best fit for remaining courses
                if min(type_counts) > max(len(courses) / len(spread_semesters) * 2, 5):
                    break
    
        # Place any remaining courses in best available semesters
        for course in remaining_courses:
            best_idx = self._find_best_semester_for_standalone(course, spread_semesters)
            if best_idx >= 0:
                spread_semesters[best_idx]["classes"].append(course)
                spread_semesters[best_idx]["totalCredits"] = spread_semesters[best_idx].get("totalCredits", 0) + course.get("credits", 0)
                logger.info(f"Placed remaining {course_type} course {course['class_number']} in semester {best_idx+1}")

    def _find_best_semester_for_standalone(self, course: Dict, 
                                     spread_semesters: List[Dict]) -> int:
        """Find the best semester for a standalone course considering balance"""
        valid_semesters = []
        
        # First check semester offerings constraint
        for idx, semester in enumerate(spread_semesters):
            if semester["type"] in course.get("semesters_offered", []):
                # Check prerequisites
                if self._prerequisites_satisfied_before_semester_dict(
                    course, spread_semesters, idx):
                    valid_semesters.append(idx)
    
        if not valid_semesters:
            return -1  # No valid semester found
        
        # Score each valid semester based on balance criteria
        best_score = -1
        best_idx = -1
        
        for idx in valid_semesters:
            semester = spread_semesters[idx]
            
            # Count courses by type in this semester
            religion_count = sum(1 for c in semester["classes"] 
                              if c.get("course_type") == "religion")
            major_count = sum(1 for c in semester["classes"] 
                            if c.get("course_type") == "major")
            minor_count = sum(1 for c in semester["classes"] 
                            if c.get("course_type") == "minor")
            
            # Calculate credit load if we add this course
            total_credits = semester.get("totalCredits", 0) + course.get("credits", 0)
            
            # Calculate score based on balanced distribution
            score = 0
            
            # Prefer semesters with fewer courses of the same type
            if course.get("course_type") == "religion":
                score -= religion_count * 10  # Strongly avoid multiple religion courses
            elif course.get("course_type") == "major":
                score -= major_count * 3      # Avoid too many major courses
            elif course.get("course_type") == "minor":
                score -= minor_count * 3      # Avoid too many minor courses
            
            # Prefer semesters with fewer courses overall
            score -= len(semester["classes"]) * 2
            
            # Prefer semesters with more room for credits
            credit_limit = semester.get("creditLimit", 18)
            credit_room = credit_limit - total_credits
            if credit_room >= 0:
                score += credit_room
            else:
                score -= 100  # Strong penalty for exceeding credit limit
            
            if score > best_score:
                best_score = score
                best_idx = idx
        
        return best_idx

    def _prerequisites_satisfied_before_semester_dict(self, course: Dict, 
                                               scheduled_semesters: List[Dict], 
                                               semester_idx: int) -> bool:
        """Check if prerequisites are satisfied in previous semesters"""
        # No prerequisites
        if not course.get("prerequisites", []):
            return True
        
        # Check all previous semesters
        scheduled_ids = set()
        for i in range(semester_idx):
            for c in scheduled_semesters[i]["classes"]:
                scheduled_ids.add(c["id"])
    
        return all(prereq_id in scheduled_ids for prereq_id in course.get("prerequisites", []))