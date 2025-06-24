window.addEventListener('DOMContentLoaded', async () => {
    // Add a global map to store all classes by ID for quick lookup
    let allClassesLookup = {};

    // Fetch ALL classes to build a lookup map. This is crucial because
    // prerequisites/corequisites might refer to classes not part of the
    // currently viewed course's 'data' object.
    try {
        const allClassesResponse = await fetch('/api/classes');
        if (!allClassesResponse.ok) {
            throw new Error(`Error fetching all classes: ${allClassesResponse.statusText}`);
        }
        const allFetchedClasses = await allClassesResponse.json();
        allClassesLookup = allFetchedClasses.reduce((map, cls) => {
            if (cls.id) map[cls.id] = cls;
            return map;
        }, {});
        console.log("Built allClassesLookup:", allClassesLookup); // Debugging
    } catch (error) {
        console.error("Failed to fetch all classes for lookup:", error);
        // Continue without comprehensive lookup if fetch fails, some corequisite details might be missing
    }

    // Example function that renders course sections and classes
    // This function is still present but its direct use might be minimal now
    // as displayCourse directly renders to courseSectionsDiv.
    function renderCourseSections(courseData) {
        const courseSections = document.getElementById('course-sections');
        courseSections.innerHTML = '';

        courseData.sections.forEach(section => {
            const sectionDiv = document.createElement('div');
            sectionDiv.innerHTML = `<h3>${section.section_name}</h3>`;

            section.classes.forEach(cls => {
                const classDiv = document.createElement('div');
                // Add credits beside the course name here
                classDiv.innerHTML = `
                    <span>${cls.class_name} (${cls.class_number})</span>
                    <span style="margin-left: 10px; color: #888;">Credits: ${cls.credits}</span>
                `;
                sectionDiv.appendChild(classDiv);
            });

            courseSections.appendChild(sectionDiv);
        });
    }

    const urlParams = new URLSearchParams(window.location.search);
    const courseId = urlParams.get('course_id');
    const courseInfoDiv = document.getElementById('course-info');
    const courseSectionsDiv = document.getElementById('course-sections');
    const addSectionButton = document.getElementById('add-section-button');
    const addSectionModal = document.getElementById('add-section-modal');
    const addSectionForm = document.getElementById('add-section-form');
    const sectionTypeSelect = document.getElementById('section-type');
    const electiveOptions = document.getElementById('elective-options');
    const deleteCourseButton = document.getElementById('delete-course-button');
    const editCourseModal = document.getElementById('edit-course-modal');
    const editCourseForm = document.getElementById('edit-course-form');
    const editCourseButton = document.getElementById('edit-course-button');
    const editSectionModal = document.getElementById('edit-section-modal');
    const editSectionForm = document.getElementById('edit-section-form');
    const editSectionTypeSelect = document.getElementById('edit-section-type');
    const editElectiveOptions = document.getElementById('edit-elective-options');
    let searchTimeout;
    
    if (deleteCourseButton) {
        deleteCourseButton.addEventListener('click', async () => {
            if (!confirm('Are you sure you want to delete this course?')) return;
            try {
                const response = await fetch(`/api/courses/${courseId}`, {
                    method: 'DELETE'
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Failed to delete course');
                }
               
                window.location.href = 'search.html'; // Redirect to search after deletion
            } catch (error) {
                console.error('Error deleting course:', error);
                alert(`Error: ${error.message}`);
            }
        });
    }

    if (editCourseButton) {
        editCourseButton.addEventListener('click', async () => {
            try {
                const response = await fetch(`/api/courses/${courseId}`);
                if (!response.ok) throw new Error('Failed to fetch course details');
                const courseData = await response.json();
                
                // Populate the form with current values
                document.getElementById('edit-course-name').value = courseData.course_name;
                document.getElementById('edit-course-type').value = courseData.course_type;
                
                // Handle holokai field
                const editHolokaiContainer = document.getElementById('edit-holokai-container');
                const editHolokaiSelect = document.getElementById('edit-holokai-type');
                
                // Show/hide holokai dropdown based on course type
                const courseType = courseData.course_type.toLowerCase();
                if (courseType === 'major' || courseType === 'minor') {
                    editHolokaiContainer.style.display = 'block';
                    editHolokaiSelect.value = courseData.holokai || '';
                } else {
                    editHolokaiContainer.style.display = 'none';
                }
                
                // Show the modal
                editCourseModal.style.display = 'block';
            } catch (error) {
                console.error('Error fetching course details:', error);
                alert('Error loading course details');
            }
        });
    }

    // Add event listener to show/hide holokai field based on course type
    document.getElementById('edit-course-type').addEventListener('change', function() {
        const courseType = this.value.toLowerCase();
        const editHolokaiContainer = document.getElementById('edit-holokai-container');
        
        if (courseType === 'major' || courseType === 'minor') {
            editHolokaiContainer.style.display = 'block';
        } else {
            editHolokaiContainer.style.display = 'none';
        }
    });

    editCourseForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const courseType = document.getElementById('edit-course-type').value;
        const updatedData = {
            course_name: document.getElementById('edit-course-name').value,
            course_type: courseType
        };
        
        // Only include holokai if course type is major or minor
        if (courseType.toLowerCase() === 'major' || courseType.toLowerCase() === 'minor') {
            updatedData.holokai = document.getElementById('edit-holokai-type').value;
        }
    
        try {
            const response = await fetch(`/api/courses/${courseId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updatedData)
            });
    
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update course');
            }
            
            // Hide modal and refresh page to show updated data
            editCourseModal.style.display = 'none';
            location.reload();
        } catch (error) {
            console.error('Error updating course:', error);
            alert(error.message);
        }
    });
    
    document.getElementById('cancel-edit-course').addEventListener('click', () => {
        editCourseModal.style.display = 'none';
        editCourseForm.reset();
    });
    
    window.addEventListener('click', (event) => {
        if (event.target === editCourseModal) {
            editCourseModal.style.display = 'none';
            editCourseForm.reset();
        }
    });

    if (!courseId) {
        courseInfoDiv.innerHTML = '<p>No valid course found.</p>';
        return;
    }

    // Show/hide elective options based on section type
    sectionTypeSelect.addEventListener('change', () => {
        electiveOptions.style.display = 
            sectionTypeSelect.value === 'elective' ? 'block' : 'none';
    });

    // Handle section modal
    addSectionButton.addEventListener('click', () => {
        addSectionModal.style.display = 'block';
    });

    document.getElementById('cancel-section').addEventListener('click', () => {
        addSectionModal.style.display = 'none';
        addSectionForm.reset();
    });

    // Handle section form submission
    addSectionForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const sectionData = {
            section_name: document.getElementById('section-name').value,
            is_required: sectionTypeSelect.value === 'required',
            credits_needed_to_take: sectionTypeSelect.value === 'elective' ? 
                parseInt(document.getElementById('classes-to-choose').value) : null
        };

        try {
            const response = await fetch(`/api/courses/${courseId}/sections`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(sectionData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to create section');
            }
            
            addSectionModal.style.display = 'none';
            addSectionForm.reset();
            location.reload();
        } catch (error) {
            console.error('Error creating section:', error);
            alert(error.message);
        }
    });

    try {
        // Fetch course details with sections
        const response = await fetch(`/api/courses/${encodeURIComponent(courseId)}`);
        if (!response.ok) {
            throw new Error(`Failed to fetch course details: ${response.statusText}`);
        }
        const data = await response.json();
        if (!data) {
            courseInfoDiv.innerHTML = '<p>No details available for this course.</p>';
            return;
        }

        // Display course info
        displayCourse(data);

    } catch (error) {
        console.error(error);
        courseInfoDiv.innerHTML = `<p>Error: ${error.message}</p>`;
    }

    // First, inject the search modal HTML
    const searchModalHTML = `
        <div id="search-modal" class="modal">
            <div class="modal-content search-modal-content">
                <h2>Search Classes</h2>
                <input type="text" class="class-search-input" placeholder="Search by Class Number">
                <ul class="search-results"></ul>
                <div class="modal-buttons">
                    <button id="close-search-modal">Cancel</button>
                </div>
            </div>
        </div>`;
    document.body.insertAdjacentHTML('beforeend', searchModalHTML);

    // Now that the modal exists in the DOM, set up the search functionality
    const searchModal = document.getElementById('search-modal');
    const searchInput = searchModal.querySelector('.class-search-input');
    const searchResults = searchModal.querySelector('.search-results');

    // Add input event listener to search input
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const sectionId = searchModal.dataset.sectionId;
        searchTimeout = setTimeout(() => performSearch(sectionId), 500);
    });

    // Add modal close handlers
    document.getElementById('close-search-modal').onclick = () => {
        searchModal.style.display = 'none';
    };

    window.onclick = (event) => {
        if (event.target === searchModal) {
            searchModal.style.display = 'none';
        }
    };

    function displayCourse(data) {
        // Calculate total credits in the course
        let totalCredits = 0;
        // Set to keep track of unique class IDs already added to totalCredits
        const countedClassIds = new Set();
        
        if (data.sections && Array.isArray(data.sections)) {
            data.sections.forEach(section => {
                if (section.classes && Array.isArray(section.classes)) {
                    section.classes.forEach(cls => {
                        // Add main class credits only if not already counted
                        if (!countedClassIds.has(cls.id)) {
                            totalCredits += Number(cls.credits || 0);
                            countedClassIds.add(cls.id);
                        }

                        // Add corequisite credits
                        // NOTE: Corequisite credits are only counted for the individual class display,
                        // NOT for the overall course totalCredits at the top.
                    });
                }
            });
        }
        
        // Update the HTML to include credits and holokai
        courseInfoDiv.innerHTML = `
        <h2>${data.course_name} <span class="course-credits">•   ${totalCredits} Credits</span></h2>
        <h3>${data.course_type || 'N/A'}</h3>
        ${data.course_type && (data.course_type.toLowerCase() === 'major' || data.course_type.toLowerCase() === 'minor') ? 
            `<h4>Holokai Section: ${data.holokai || 'None'}</h4>` : ''}
        <div class="editanddelete">
            <img id="edit-course-button" src="./assets/whiteedit.png" alt="Edit course">
            <img id="download-course-button" src="./assets/downloadcourse.png" alt="Download course">
            <img id="delete-course-button" src="./assets/whitedelete.png" alt="Delete course">
            <img id="copy-course-button" src="./assets/copy-button.png" alt="Duplicate course">
        </div>
    `;

        // Add this right after setting courseInfoDiv.innerHTML
        const editButton = document.getElementById('edit-course-button');
        if (editButton) {
            editButton.addEventListener('click', async () => {
                try {
                    const response = await fetch(`/api/courses/${courseId}`);
                    if (!response.ok) throw new Error('Failed to fetch course details');
                    const courseData = await response.json();
                    
                    // Populate the form with current values
                    document.getElementById('edit-course-name').value = courseData.course_name;
                    document.getElementById('edit-course-type').value = courseData.course_type;
                    
                    // Handle holokai field
                    const editHolokaiContainer = document.getElementById('edit-holokai-container');
                    const editHolokaiSelect = document.getElementById('edit-holokai-type');
                    
                    // Show/hide holokai dropdown based on course type
                    const courseType = courseData.course_type.toLowerCase();
                    if (courseType === 'major' || courseType === 'minor') {
                        editHolokaiContainer.style.display = 'block';
                        editHolokaiSelect.value = courseData.holokai || '';
                    } else {
                        editHolokaiContainer.style.display = 'none';
                    }
                    
                    // Show the modal
                    editCourseModal.style.display = 'block';
                } catch (error) {
                    console.error('Error fetching course details:', error);
                    alert('Error loading course details');
                }
            });
        }

    
        if (editButton) {
            editButton.addEventListener('click', function() {
                const editAndDelete = this.closest('.editanddelete');
                editAndDelete.classList.toggle('active');
                this.classList.toggle('active');
            });
        }
        const deleteButton = document.getElementById('delete-course-button');
        if (deleteButton) {
            deleteButton.addEventListener('click', async () => {
                if (confirm('Are you sure you want to delete this course? This action cannot be undone.')) {
                    try {
                        const response = await fetch(`/api/courses/${courseId}`, {
                            method: 'DELETE'
                        });

                        if (!response.ok) {
                            const errorData = await response.json();
                            throw new Error(errorData.error || 'Failed to delete course');
                        }

                        // Redirect to search page after successful deletion
                        window.location.href = 'search.html';
                    } catch (error) {
                        console.error('Error deleting course:', error);
                        alert('Error deleting course: ' + error.message);
                    }
                }
            });
        }
        const copyButton = document.getElementById('copy-course-button');
        if (copyButton) {
            copyButton.addEventListener('click', async () => {
                if (confirm('Do you want to create a copy of this course with all its sections and classes?')) {
                    try {
                        // Show loading state
                        copyButton.style.opacity = '0.5';
                        copyButton.style.cursor = 'wait';
                        
                        const response = await fetch(`/api/courses/${courseId}/duplicate`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' }
                        });

                        if (!response.ok) {
                            const errorData = await response.json();
                            throw new Error(errorData.error || 'Failed to copy course');
                        }

                        const newCourse = await response.json();
                        
                        // Success message and redirect to the new course
                        alert(`Course copied successfully! The new course is named "${newCourse.course_name}".`);
                        window.location.href = `course_details.html?course_id=${newCourse.id}`;
                    } catch (error) {
                        console.error('Error copying course:', error);
                        alert('Error copying course: ' + error.message);
                        
                        // Reset button state
                        copyButton.style.opacity = '1';
                        copyButton.style.cursor = 'pointer';
                    }
                }
            });
        }

        // Clear the sections div
        courseSectionsDiv.innerHTML = '';

        if (data.sections && Array.isArray(data.sections) && data.sections.length > 0) {
            data.sections.forEach((section, index) => {
                if (section && section.id) {
                    const sectionDiv = document.createElement('div');
                    sectionDiv.className = 'course-section';
                    sectionDiv.draggable = true; // Make draggable
                    sectionDiv.dataset.sectionId = section.id;
                    sectionDiv.dataset.index = index;
                    
                    // Add the drag handle
                    sectionDiv.innerHTML = `
                        <div class="drag-handle"></div>
                        <div class="section-header">
                            <div class="section-info-container">
                                <h3 class="section-title">
                                    ${section.section_name}
                                    <img class="section-icon" src="./assets/editclassbutton.png" alt="Edit section" data-section="${section.id}">
                                </h3>
                                <div class="section-info">
                                    ${section.is_required ? 'Required' : `Take a total of ${section.credits_needed_to_take} credits`}
                                </div>
                            </div>
                            <div class="section-header-actions">
                                <button class="delete-section-button" data-section="${section.id}">Delete This Section</button>
                                <img class="toggle-actions-button" src="./assets/editclassbutton.png" alt="Toggle actions" data-section="${section.id}">
                            </div>
                            

                        </div>
                        <ul class="classes-list" id="section-${section.id}-classes"></ul>
                        <div class="section-footer">
                            <div class="section-controls">
                                <div class="custom-button add-existing-class-button" data-section="${section.id}">
                                    <img src="./assets/addexistingclassbutton.png" alt="Add existing">
                                    <span>Add Existing Class</span>
                                </div>
                                <div class="custom-button add-new-class-button" data-section="${section.id}">
                                    <img src="./assets/addnewclassbutton.png" alt="Add new">
                                    <span>Add New Class</span>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    courseSectionsDiv.appendChild(sectionDiv);
                    
                    // Display classes for this section...
                    const sectionClassesList = document.getElementById(`section-${section.id}-classes`);
                    if (section.classes && section.classes.length > 0) {
                        section.classes.forEach(cls => {
                            let baseCredits = cls.credits || 0;
                            let creditsDisplay = `${baseCredits} cr.`; // Start with the class's own credits

                            // Calculate total corequisite credits to display with the class
                            let totalCorequisiteCredits = 0; 
                            if (cls.corequisites && cls.corequisites.length > 0) {
                                cls.corequisites.forEach(coreq => {
                                    const coreqId = typeof coreq === 'object' ? coreq.id : coreq;
                                    const coreqClass = allClassesLookup[coreqId];
                                    if (coreqClass) {
                                        totalCorequisiteCredits += (coreqClass.credits || 0);
                                    }
                                });
                            }

                            // Append corequisite info if corequisites exist and have credits
                            if (totalCorequisiteCredits > 0) {
                                creditsDisplay += ` + ${totalCorequisiteCredits} cr. Co-requisite`;
                            }

                            const li = document.createElement('li');
                            // Add a class for styling if necessary and a data attribute for easier access
                            li.className = 'class-item-clickable'; // Add a class for styling/cursor
                            li.dataset.classId = cls.id; // Store class ID for lookup if needed
                            li.style.cursor = 'pointer'; // Indicate it's clickable

                            li.innerHTML = `
                                <span>${cls.class_number}: ${cls.class_name}</span>
                                <div class="class-right-content">
                                    <span class="class-credits-display">${creditsDisplay}</span>
                                    <div class="class-actions-buttons">
                                        <img class="update-class-button"
                                            src="./assets/editclassbutton.png"
                                            alt="Edit class"
                                            data-class-id="${cls.id}"
                                            data-section-id="${section.id}">
                                        <img class="delete-class-button"
                                            src="./assets/removebutton.png"
                                            alt="Remove class"
                                            data-class-id="${cls.id}"
                                            data-section-id="${section.id}">
                                    </div>
                                </div>
                            `;
                            sectionClassesList.appendChild(li);

                            // Add the click event listener to show the details popup
                            li.addEventListener('click', () => {
                                // Find the class data using its ID from the global lookup
                                const clickedClassData = allClassesLookup[cls.id];
                                if (clickedClassData) {
                                    showClassDetails(clickedClassData);
                                } else {
                                    console.error('Class data not found for ID:', cls.id);
                                }
                            });
                        });
                    } else {
                        sectionClassesList.innerHTML = '<li>No classes in this section</li>';
                    }
                }
            });
    
            // Add event listeners for the section-specific buttons
            attachSectionEventListeners();
            
            // Add drag and drop functionality
            initDragAndDrop();
        }
    
        // Show add section button (always visible)
        addSectionButton.style.display = 'block';
    }

    // Attach event listeners for section controls
    function attachSectionEventListeners() {
        // Add existing class buttons
        document.querySelectorAll('.add-existing-class-button').forEach(button => {
            button.addEventListener('click', (e) => {
                // Get the section ID from the button element itself, not the target
                const sectionId = button.dataset.section;
                showSearchContainer(sectionId);
            });
        });

        // Add new class buttons
        document.querySelectorAll('.add-new-class-button').forEach(button => {
            button.addEventListener('click', (e) => {
                // Get sectionId from the button's data attribute, not from e.target
                const sectionId = button.dataset.section;
                window.location.href = `add_new_class.html?course_id=${courseId}&section_id=${sectionId}`;
            });
        });

        // Update class buttons
        document.querySelectorAll('.update-class-button').forEach(button => {
            button.addEventListener('click', (e) => {
                const classId = e.target.dataset.classId;
                const sectionId = e.target.dataset.sectionId;
                window.location.href = `edit_class.html?course_id=${courseId}&class_id=${classId}&section_id=${sectionId}`;
            });
        });

        // Delete class buttons
                document.querySelectorAll('.delete-class-button').forEach(button => {
            button.addEventListener('click', async (e) => {
                const classId = e.target.dataset.classId;
                const sectionId = e.target.dataset.sectionId;
                
                if (confirm('Are you sure you want to remove this class from the section?')) {
                    try {
                        // Update the URL to match the API endpoint
                        const response = await fetch(
                            `/api/courses/${courseId}/sections/${sectionId}/classes/${classId}`,
                            { method: 'DELETE' }
                        );
        
                        if (!response.ok) {
                            const errorData = await response.json();
                            throw new Error(errorData.error || 'Failed to remove class from section');
                        }
        
                        location.reload();
                    } catch (error) {
                        console.error('Error removing class from section:', error);
                        alert(error.message);
                    }
                }
            });
        });

        // Delete section buttons
        document.querySelectorAll('.delete-section-button').forEach(button => {
            button.addEventListener('click', async (e) => {
                const sectionId = e.target.dataset.section;
                
                if (confirm('Are you sure you want to delete this section? This will remove all class associations.')) {
                    try {
                        const response = await fetch(
                            `/api/courses/${courseId}/sections/${sectionId}`,
                            { method: 'DELETE' }
                        );

                        if (!response.ok) {
                            const errorData = await response.json();
                            throw new Error(errorData.error || 'Failed to delete section');
                        }

                        location.reload();
                    } catch (error) {
                        console.error('Error deleting section:', error);
                        alert(error.message);
                    }
                }
            });
        });

        // Add search input listeners for each section
        document.querySelectorAll('.class-search-input').forEach(input => {
            input.addEventListener('input', (e) => {
                const sectionId = e.target.closest('.section-controls')
                    .querySelector('.add-existing-class-button').dataset.section;
                
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => performSearch(sectionId), 500);
            });
        });

        // Add this to your attachSectionEventListeners function
        document.querySelectorAll('.section-icon').forEach(button => {
            button.addEventListener('click', async (e) => {
                const sectionId = e.target.dataset.section;
                
                try {
                    // Fetch current section data
                    const response = await fetch(`/api/courses/${courseId}/sections/${sectionId}`);
                    if (!response.ok) throw new Error('Failed to fetch section details');
                    const sectionData = await response.json();
                    
                    // Populate the form with current values
                    document.getElementById('edit-section-name').value = sectionData.section_name;
                    document.getElementById('edit-section-type').value = sectionData.is_required ? 'required' : 'elective';
                    
                    if (!sectionData.is_required) {
                        document.getElementById('edit-classes-to-choose').value = sectionData.credits_needed_to_take || 1;
                        editElectiveOptions.style.display = 'block';
                    } else {
                        editElectiveOptions.style.display = 'none';
                    }
                    
                    // Set the section ID in the hidden field
                    document.getElementById('edit-section-id').value = sectionId;
                    
                    // Show the modal
                    editSectionModal.style.display = 'block';
                } catch (error) {
                    console.error('Error fetching section details:', error);
                    alert('Error loading section details');
                }
            });
        });

        // Add this to your attachSectionEventListeners function
        document.querySelectorAll('.toggle-actions-button').forEach(button => {
            button.addEventListener('click', (e) => {
                const sectionId = e.target.dataset.section;
                const classList = document.getElementById(`section-${sectionId}-classes`);
                const sectionElement = e.target.closest('.course-section');
                
                // Toggle the show-actions class on the section's classes list
                classList.classList.toggle('show-actions');
                
                // Toggle active class on the section element to show/hide admin actions
                sectionElement.classList.toggle('active');
                
                // Toggle the active class on the button itself
                e.target.style.transform = classList.classList.contains('show-actions') ? 
                    'rotate(180deg)' : 'rotate(0deg)';
            });
        });
    }

    // Show/hide elective options based on section type selection
    editSectionTypeSelect.addEventListener('change', () => {
        editElectiveOptions.style.display = 
            editSectionTypeSelect.value === 'elective' ? 'block' : 'none';
    });

    // Handle modal close
    document.getElementById('cancel-edit-section').addEventListener('click', () => {
        editSectionModal.style.display = 'none';
        editSectionForm.reset();
    });

    // Close modal on outside click
    window.addEventListener('click', (event) => {
        if (event.target === editSectionModal) {
            editSectionModal.style.display = 'none';
            editSectionForm.reset();
        }
    });

    // Handle form submission
    editSectionForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const sectionId = document.getElementById('edit-section-id').value;
        const isElective = editSectionTypeSelect.value === 'elective';
        
        const updatedData = {
            section_name: document.getElementById('edit-section-name').value,
            is_required: !isElective,
            credits_needed_to_take: isElective ? 
                parseInt(document.getElementById('edit-classes-to-choose').value) : null
        };

        try {
            const response = await fetch(`/api/courses/${courseId}/sections/${sectionId}`, {
                method: 'PUT', 
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updatedData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update section');
            }
            
            // Hide modal and refresh page to show updated data
            editSectionModal.style.display = 'none';
            location.reload();
        } catch (error) {
            console.error('Error updating section:', error);
            alert(error.message);
        }
    });

    function showSearchContainer(sectionId) {
        const searchModal = document.getElementById('search-modal');
        const searchInput = searchModal.querySelector('.class-search-input');
        const searchResults = searchModal.querySelector('.search-results');
        
        // Store the section ID as a data attribute
        searchModal.dataset.sectionId = sectionId;
        
        // Clear previous results
        searchInput.value = '';
        searchResults.innerHTML = '';
        
        // Show the modal
        searchModal.style.display = 'block';
        searchInput.focus();
    }

    async function performSearch(sectionId) {
        const searchModal = document.getElementById('search-modal');
        const searchInput = searchModal.querySelector('.class-search-input');
        const searchResults = searchModal.querySelector('.search-results');
        const query = searchInput.value.trim();
        console.log('Performing search with query:', query); // Debug log
        if (!query) {
            searchResults.innerHTML = '';
            return;
        }
        try {
            const response = await fetch(`/api/classes/search?query=${encodeURIComponent(query)}`);
            console.log('Search response:', response); // Debug log
            
            if (!response.ok) throw new Error('Search failed');

            const data = await response.json();
            console.log('Search results:', data); // Debug log
            
            displaySearchResults(data.classes, sectionId, searchResults);
        } catch (error) {
            console.error('Search error:', error);
            searchResults.innerHTML = '<li class="error">Search failed. Please try again.</li>';
        }
    }

    function displaySearchResults(classes, sectionId, searchResults) {
        console.log('Adding class with:', {
            courseId: courseId,
            sectionId: sectionId,
            classes: classes
        });

        searchResults.innerHTML = '';
        if (!classes.length) {
            searchResults.innerHTML = '<li>No classes found</li>';
            return;
        }

        classes.forEach(cls => {
            const li = document.createElement('li');
            li.innerHTML = `
                ${cls.class_number}: ${cls.class_name}
                <button class="add-class-button" 
                    data-class-id="${cls.id}" 
                    data-section-id="${sectionId}">Add</button>
            `;
            searchResults.appendChild(li);
        });

        // Update the event listeners for add buttons
        searchResults.querySelectorAll('.add-class-button').forEach(button => {
            button.addEventListener('click', async (e) => {
                const classId = button.dataset.classId;
                const sectionId = button.dataset.sectionId;
                
                console.log('Adding class:', {
                    courseId: courseId,
                    sectionId: sectionId,
                    classId: classId
                });

                try {
                    const response = await fetch(
                        `/api/courses/${courseId}/sections/${sectionId}/classes`, 
                        {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ class_id: classId })
                        }
                    );

                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.error || 'Failed to add class');
                    }

                    location.reload();
                } catch (error) {
                    console.error('Error adding class:', error);
                    alert(error.message);
                }
            });
        });
    }

    // Function to initialize drag and drop
    function initDragAndDrop() {
        const sections = document.querySelectorAll('.course-section');
        let draggedSection = null;
        
        sections.forEach(section => {
            // Drag start event
            section.addEventListener('dragstart', (e) => {
                draggedSection = section;
                setTimeout(() => {
                    section.classList.add('dragging');
                }, 0);
                
                // Set data transfer for drag operation
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', section.dataset.sectionId);
            });
            
            // Drag end event
            section.addEventListener('dragend', () => {
                section.classList.remove('dragging');
                draggedSection = null;
                
                // Save the new order to the database
                saveNewSectionOrder();
            });
            
            // Drag over event - needed to allow dropping
            section.addEventListener('dragover', (e) => {
                e.preventDefault();
                if (draggedSection === section) return;
                
                const box = section.getBoundingClientRect();
                const offsetY = e.clientY - box.top - (box.height / 2);
                
                // Determine if we're before or after this section
                if (offsetY < 0) {
                    section.classList.add('drag-over-top');
                    section.classList.remove('drag-over-bottom');
                } else {
                    section.classList.add('drag-over-bottom');
                    section.classList.remove('drag-over-top');
                }
            });
            
            // Drag enter event
            section.addEventListener('dragenter', (e) => {
                e.preventDefault();
                if (draggedSection === section) return;
            });
            
            // Drag leave event
            section.addEventListener('dragleave', () => {
                section.classList.remove('drag-over-top', 'drag-over-bottom');
            });
            
            
            // Drop event
            section.addEventListener('drop', (e) => {
                e.preventDefault();
                if (draggedSection === section) return;
                
                section.classList.remove('drag-over-top', 'drag-over-bottom');
                
                const box = section.getBoundingClientRect();
                const offsetY = e.clientY - box.top - (box.height / 2);
                
                if (offsetY < 0) {
                    // Drop before this section
                    courseSectionsDiv.insertBefore(draggedSection, section);
                } else {
                    // Drop after this section
                    courseSectionsDiv.insertBefore(draggedSection, section.nextSibling);
                }
            });
        });
    }

    // Function to save the new section order - DIRECT URL APPROACH
    async function saveNewSectionOrder() {
        try {
            // Get all sections in their current DOM order
            const sections = document.querySelectorAll('.course-section');
            
            if (!sections || sections.length === 0) {
                console.log('No sections found to reorder');
                return;
            }
            
            // Ensure course ID is a pure number, not a string
            const courseIdInt = parseInt(courseId, 10);
            
            if (isNaN(courseIdInt) || courseIdInt <= 0) {
                throw new Error('Invalid course ID');
            }
            
            // Build section data manually with explicit integers
            const sectionDataArray = [];
            
            // Use explicit loop to process each section
            for (let i = 0; i < sections.length; i++) {
                const sectionIdRaw = sections[i].dataset.sectionId;
                const sectionIdInt = parseInt(sectionIdRaw, 10);
                
                if (isNaN(sectionIdInt) || isNaN(sectionIdInt)) { // Removed isNaN(sectionIdInt) || isNaN(sectionIdInt)
                    console.warn(`Skipping invalid section ID: ${sectionIdRaw}`);
                    continue;
                }
                
                sectionDataArray.push({
                    section_id: sectionIdInt,
                    display_order: i + 1
                });
            }
            
            // For debugging - print the exact request we're about to send
            const requestBody = JSON.stringify({
                sections: sectionDataArray
            });
            
            console.log(`Sending request to /api/courses/${courseIdInt}/sections/reorder`);
            console.log(`Request body: ${requestBody}`);
            
            // Make the request without any transformations after this point
            const response = await fetch(`/api/courses/${courseIdInt}/sections/reorder`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: requestBody
            });
            
            // Get and log the raw response
            const responseText = await response.text();
            console.log('Raw API Response:', responseText);
            
            if (response.ok) {
                console.log('Section order updated successfully');
                return true;
            } else {
                let errorMessage = 'Failed to update section order';
                try {
                    const errorData = JSON.parse(responseText);
                    errorMessage = errorData.error || errorMessage;
                } catch (e) {
                    errorMessage = responseText || errorMessage;
                }
                throw new Error(errorMessage);
            }
        } catch (error) {
            console.error('Error saving section order:', error);
            alert('Error: ' + error.message);
            return false;
        }
    }

    // Only use this if the above doesn't work
    async function saveNewSectionOrderAlternative() {
        try {
            // Get all sections and their order
            const sections = document.querySelectorAll('.course-section');
            
            if (!sections || sections.length === 0) {
                return;
            }
            
            // Save each section order individually instead of in batch
            for (let i = 0; i < sections.length; i++) {
                const sectionId = parseInt(sections[i].dataset.sectionId, 10);
                const displayOrder = i + 1;
                
                // Skip invalid IDs
                if (isNaN(sectionId)) continue;
                
                // Make individual update request for each section
                await fetch(`/api/courses/${parseInt(courseId, 10)}/sections/${sectionId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        display_order: displayOrder
                    })
                });
            }
            
            console.log('All sections updated individually');
            return true;
        } catch (error) {
            console.error('Error in individual updates:', error);
            return false;
        }
    }

    // NEW: Function to show class details popup
    function showClassDetails(classData) {
        // Remove any existing popups
        const existingPopup = document.querySelector('.class-details-popup');
        const existingOverlay = document.querySelector('.popup-overlay');
        if (existingPopup) existingPopup.remove();
        if (existingOverlay) existingOverlay.remove();

        // Create overlay
        const overlay = document.createElement('div');
        overlay.className = 'popup-overlay';
        document.body.appendChild(overlay);

        // Create popup
        const popup = document.createElement('div');
        popup.className = 'class-details-popup';

        // Helper function to get class number from ID using allClassesLookup
        const getClassNameFromId = (id) => {
            const cls = allClassesLookup[id];
            return cls ? `${cls.class_number}` : 'Unknown Class';
        };

        // Format prerequisites and corequisites with class numbers
        const prerequisites = Array.isArray(classData.prerequisites) && classData.prerequisites.length > 0
            ? classData.prerequisites.map(p => getClassNameFromId(typeof p === 'object' ? p.id : p)).join(', ')
            : 'None';
        
        const corequisites = Array.isArray(classData.corequisites) && classData.corequisites.length > 0
            ? classData.corequisites.map(c => getClassNameFromId(typeof c === 'object' ? c.id : c)).join(', ')
            : 'None';

        // Determine the content for the link section
        // Use a conditional (ternary) operator to decide whether to create an <a> tag
        const linkContent = (classData.link && classData.link.startsWith('http'))
            ? `<a href="${classData.link}" target="_blank" rel="noopener noreferrer">${classData.link}</a>`
            : (classData.link || 'No link available.');


        popup.innerHTML = `
            <button class="close-button">&times;</button>
            <h2>${classData.class_number} - ${classData.class_name}</h2>
            
            <div class="details-section">
                <h3>Description</h3>
                <p>${classData.description || 'No description available.'}</p>
            </div>
            
            <div class="details-section">
                <h3>Credit Hours</h3>
                <p>${classData.credits || 3} credits</p>
            </div>
            
            <div class="details-section">
                <h3>Prerequisites</h3>
                <p>${prerequisites}</p>
            </div>
            
            <div class="details-section">
                <h3>Corequisites</h3>
                <p>${corequisites}</p>
            </div>
            
            <div class="details-section">
                <h3>Link</h3>
                <p>${linkContent}</p>
            </div>
        `;

        // Add to document
        document.body.appendChild(popup);

        // Add close handlers
        const closePopup = () => {
            popup.remove();
            overlay.remove();
        };

        popup.querySelector('.close-button').addEventListener('click', closePopup);
        overlay.addEventListener('click', closePopup);

        // Stop click event from bubbling to overlay when clicking popup
        popup.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    }
});
