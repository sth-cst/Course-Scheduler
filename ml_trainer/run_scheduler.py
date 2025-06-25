import json
import logging
from typing import Dict, List
from constraint_optimizer import ScheduleOptimizer, Course  # Add Course here
from semester_based_optimizer import SemesterBasedOptimizer
from data_processor import ScheduleDataProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def build_prereq_tree(courses: List[Course]) -> Dict:
    """Build a tree structure starting from root prerequisites"""
    tree = {}
    processed = set()
    
    def add_course_as_root(course: Course, tree: Dict):
        """Add a course and all courses that depend on it"""
        if course.class_number not in tree and course.class_number not in processed:
            tree[course.class_number] = {
                "name": course.name,
                "course_type": course.course_type,
                "dependents": {}
            }
            processed.add(course.class_number)
            
            # Find all courses that have this as a prerequisite
            dependents = [c for c in courses if course.id in c.prerequisites]
            for dep in dependents:
                add_course_as_root(dep, tree[course.class_number]["dependents"])
    
    # Find all root courses (those that are prerequisites but have no prerequisites themselves)
    root_courses = [c for c in courses if not c.prerequisites and 
                   any(c.id in other.prerequisites for other in courses)]
    
    # Also include standalone courses that have no prerequisites and are not prerequisites
    standalone_courses = [c for c in courses if not c.prerequisites and 
                        not any(c.id in other.prerequisites for other in courses)]
    
    # Build trees starting from roots
    for course in root_courses:
        add_course_as_root(course, tree)
    
    # Add standalone courses at the end
    for course in standalone_courses:
        if course.class_number not in processed:
            tree[course.class_number] = {
                "name": course.name,
                "course_type": course.course_type,
                "dependents": {}
            }
    
    return tree

def print_prereq_tree(tree: Dict, indent: int = 0, prefix: str = "") -> None:
    """Print prerequisite tree with root courses on the left"""
    for i, (course_num, data) in enumerate(tree.items()):
        is_last = i == len(tree) - 1
        
        # Choose branch symbols
        symbol = "└── " if is_last else "├── "
        next_prefix = "    " if is_last else "│   "
        
        # Format course info
        type_indicator = ""
        if data["course_type"] == "religion":
            type_indicator = " [REL]"
        elif data["course_type"] == "major":
            type_indicator = " [MAJ]"
            
        # Print current course
        print(f"{prefix}{symbol}{course_num}: {data['name']}{type_indicator}")
        
        # Print dependent courses (branches)
        if data["dependents"]:
            print_prereq_tree(
                data["dependents"],
                indent + 1,
                prefix + next_prefix
            )

def print_semester_schedule(schedule: Dict, approach: str, target_semesters: int = None):
    """Print semester schedule in a more readable format"""
    print("\nSchedule Overview:")
    print("=" * 80)
    
    total_credits = 0
    for sem in schedule:
        print(f"\n{sem['type']} {sem['year']}")
        print("-" * 40)
        
        if not sem['classes']:
            print("No courses scheduled")
            continue
            
        # Group courses by type
        eil_courses = []
        prereq_courses = []
        religion_courses = []
        other_courses = []
        
        for course in sem['classes']:
            if course['class_number'] in {"STDEV 100R", "EIL 201", "EIL 313", "EIL 317", "EIL 320"}:
                eil_courses.append(course)
            elif course.get('course_type') == "religion":
                religion_courses.append(course)
            elif course.get('prerequisites'):
                prereq_courses.append(course)
            else:
                other_courses.append(course)
        
        # Print courses by group
        if eil_courses:
            print("\n  EIL Courses:")
            for course in eil_courses:
                print(f"    {course['class_number']}: {course['class_name']} ({course['credits']} cr)")
                
        if prereq_courses:
            print("\n  Prerequisite Chain Courses:")
            for course in prereq_courses:
                print(f"    {course['class_number']}: {course['class_name']} ({course['credits']} cr)")
                
        if religion_courses:
            print("\n  Religion Courses:")
            for course in religion_courses:
                print(f"    {course['class_number']}: {course['class_name']} ({course['credits']} cr)")
                
        if other_courses:
            print("\n  Other Courses:")
            for course in other_courses:
                print(f"    {course['class_number']}: {course['class_name']} ({course['credits']} cr)")
        
        print(f"\n  Total Credits: {sem['totalCredits']}")
        total_credits += sem['totalCredits']
    
    print("\nSchedule Summary:")
    print("=" * 40)
    print(f"Total Semesters: {len(schedule)}")
    if approach == "semesters-based" and target_semesters:
        print(f"Target Semesters: {target_semesters}")
    print(f"Total Credits: {total_credits}")

def print_prereq_chains(chains: List[List['Course']]):
    """Print prerequisite chains in a tree structure"""
    print("\nPrerequisite Chains:")
    print("=" * 80)
    
    for i, chain in enumerate(chains, 1):
        print(f"\nChain {i}:")
        root = chain[0]
        print(f"└── {root.class_number}: {root.name}")
        
        for depth, course in enumerate(chain[1:], 1):
            prefix = "    " * depth
            print(f"{prefix}└── {course.class_number}: {course.name}")
            
            # Show any corequisites
            if course.corequisites:
                coreq_prefix = "    " * (depth + 1)
                print(f"{coreq_prefix}├── (Corequisites)")
                for coreq_id in course.corequisites:
                    coreq = next((c for c in chain if c.id == coreq_id), None)
                    if coreq:
                        print(f"{coreq_prefix}└── {coreq.class_number}: {coreq.name}")

def run_scheduler(input_path: str, output_path: str = None):
    """Run scheduler with specified approach from payload"""
    
    # Load input payload
    with open(input_path, 'r') as f:
        payload = json.load(f)
    
    # Process data
    processor = ScheduleDataProcessor()
    processed_data = processor.process_payload(payload)
    
    # Select optimizer based on approach
    approach = processed_data["parameters"].get("approach", "credits-based")
    logger.info(f"Using scheduling approach: {approach}")
    
    if approach == "semesters-based":
        logger.info("Using SemesterBasedOptimizer")
        optimizer = SemesterBasedOptimizer()
    else:
        logger.info("Using ScheduleOptimizer")
        optimizer = ScheduleOptimizer()
        
    schedule_result = optimizer.create_schedule(processed_data)
    
    # Format into payload structure
    updated_payload = payload.copy()
    updated_payload["schedule"] = schedule_result["schedule"]
    updated_payload["metadata"] = {
        "approach": approach,
        "improvements": schedule_result.get("metadata", {}).get("improvements", []),
        "score": schedule_result.get("metadata", {}).get("score", 0),
        "startSemester": processed_data["parameters"]["startSemester"],
        "targetSemesters": processed_data["parameters"].get("targetSemesters"),
        "actualSemesters": len(schedule_result["schedule"])
    }
    
    # Display the schedule with improved formatting
    if "schedule" in schedule_result:
        print_semester_schedule(
            schedule_result["schedule"], 
            approach, 
            processed_data["parameters"].get("targetSemesters")
        )
        
        # Show prerequisite tree
        print("\nPrerequisite Tree:")
        print("=" * 80)
        all_courses = optimizer._convert_to_courses(processed_data["classes"])
        prereq_tree = build_prereq_tree(all_courses)
        print_prereq_tree(prereq_tree)
    
    # Save to output file if specified
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(updated_payload, f, indent=4)
        logger.info(f"Saved schedule to {output_path}")
    
    return updated_payload

if __name__ == "__main__":
    import sys
    
    # Allow specifying input/output files as command line arguments
    input_file = sys.argv[1] if len(sys.argv) > 1 else "Payload.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "Response.json"
    
    try:
        result = run_scheduler(input_file, output_file)
        logger.info("Schedule generation completed successfully")
    except Exception as e:
        logger.error(f"Error running scheduler: {str(e)}")
        sys.exit(1)