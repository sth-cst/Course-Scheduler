document.addEventListener('DOMContentLoaded', async () => {
    // Elements for stats box
    const statsInfo = document.getElementById('stats-info');

    const profilebutton = document.getElementById('profilebutton');
    const menubutton = document.getElementById('menubutton');

    // Elements for Search Courses box (updated)
    const courseSearchInput = document.getElementById('courseSearchInput');
    const courseSearchResults = document.getElementById('courseSearchResults');
    const addCourseButton = document.getElementById('addCourseButton');

    // Elements for Search Classes box
    const classSearchInput = document.getElementById('classSearchInput');
    const classSearchResults = document.getElementById('classSearchResults');
    const addNewClassButton = document.getElementById('addNewClassButton');

    // Load statistics (Assuming an endpoint exists; otherwise, this is a placeholder)
    const majorsCount = document.getElementById('majors-count');
    const minorsCount = document.getElementById('minors-count');
    const classesCount = document.getElementById('classes-count');

    // NEW: Get the welcome heading element
    const welcomeHeading = document.querySelector('.container header h1');

    // NEW: Function to update the welcome message
    function updateWelcomeMessage(userName = 'Guest') { // Default to 'Guest' if no name is provided
        if (welcomeHeading) {
            welcomeHeading.textContent = `Welcome, ${userName}`;
        }
    }

    // Call the function on page load.
    // Replace 'Guest' with the actual user's name once your login is integrated.
    // Example: updateWelcomeMessage(loggedInUserName);
    updateWelcomeMessage(); // Initially display "Welcome, Guest"


    // Animate a numeric count from start to end over duration (in ms)
    function animateCount(element, start, end, duration) {
        let startTime = null;
        
        function updateCount(timestamp) {
        if (!startTime) startTime = timestamp;
        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const current = Math.floor(start + (end - start) * progress);
        element.textContent = current;
        if (progress < 1) {
            window.requestAnimationFrame(updateCount);
        } else {
            element.textContent = end; // Ensure final value is exact
        }
        }
        
        window.requestAnimationFrame(updateCount);
    }

    try {
        const response = await fetch('/api/stats');
        if (response.ok) {
            const stats = await response.json();
            animateCount(majorsCount, 0, stats.majors, 200);
            animateCount(minorsCount, 0, stats.minors, 200);
            animateCount(classesCount, 0, stats.classes, 200);
        } else {
            majorsCount.textContent = '—';
            minorsCount.textContent = '—';
            classesCount.textContent = '—';
        }
    } catch (err) {
        console.error('Error fetching stats:', err);
        majorsCount.textContent = 'Error';
        minorsCount.textContent = 'Error';
        classesCount.textContent = 'Error';
    }

    // New Course Search Functionality
    let courseDebounceTimeout;
    courseSearchInput.addEventListener('input', () => {
        clearTimeout(courseDebounceTimeout);
        courseDebounceTimeout = setTimeout(() => {
            performCourseSearch();
        }, 300);
    });

    // Update performCourseSearch function to include course type
    async function performCourseSearch() {
        const query = courseSearchInput.value.trim().toLowerCase();
        courseSearchResults.innerHTML = '';

        if (query === '') return;

        try {
            const response = await fetch(`/api/courses/search?query=${encodeURIComponent(query)}&limit=5`);
            if (!response.ok) {
                let errorMessage = response.statusText;
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorMessage;
                } catch (parseError) { }
                throw new Error(`Error searching courses: ${errorMessage}`);
            }
            const data = await response.json();
            const courses = data.courses || [];

            if (courses.length === 0) {
                courseSearchResults.innerHTML = '<li>No matching programs found.</li>';
                return;
            }

            courses.forEach(course => {
                const li = document.createElement('li');
                
                // Get formatted course type
                const courseType = formatCourseType(course.course_type);
                
                // Display both name and type
                li.innerHTML = `
                    <div class="course-name">${course.course_name}</div>
                    <div class="course-type">${courseType}</div>
                `;
                
                li.addEventListener('click', () => {
                    window.location.href = `/course_details.html?course_id=${encodeURIComponent(course.id)}`;
                });
                courseSearchResults.appendChild(li);
            });

        } catch (error) {
            console.error('Error during course search:', error);
            courseSearchResults.innerHTML = `<li style="color: red;">${error.message}</li>`;
        }
    }

    // Helper function to format course type
    function formatCourseType(type) {
        // Handle case where type might be undefined
        if (!type) return '';
        
        // Format different types nicely
        switch(type.toLowerCase()) {
            case 'major':
                return 'Major';
            case 'minor':
                return 'Minor';
            case 'religion':
                return 'Religion';
            case 'eil/holokai':
                return 'EIL/Holokai';
            default:
                return type.charAt(0).toUpperCase() + type.slice(1);
        }
    }

    addCourseButton.addEventListener('click', () => {
        window.location.href = '/add_course.html';
    });

    // Search Classes Functionality
    let classDebounceTimeout;
    classSearchInput.addEventListener('input', () => {
        clearTimeout(classDebounceTimeout);
        classDebounceTimeout = setTimeout(() => {
            performClassSearch();
        }, 300);
    });

    // Fix class search results click functionality
    async function performClassSearch() {
        const query = classSearchInput.value.trim().toLowerCase();
        classSearchResults.innerHTML = '';

        if (query === '') return;

        try {
            const response = await fetch(`/api/classes/search?query=${encodeURIComponent(query)}&limit=5`);
            if (!response.ok) {
                let errorMessage = response.statusText;
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorMessage;
                } catch (parseError) { }
                throw new Error(`Error searching classes: ${errorMessage}`);
            }
            const data = await response.json();
            const classes = data.classes;

            if (!Array.isArray(classes)) {
                throw new Error('Invalid response format from server.');
            }

            if (classes.length === 0) {
                classSearchResults.innerHTML = '<li>No matching classes found.</li>';
                return;
            }

            classes.forEach(cls => {
                const li = document.createElement('li');
                // Simplify to just show class number and name
                li.textContent = `${cls.class_number}: ${cls.class_name}`;
                
                // Add click handler to the entire list item
                li.addEventListener('click', () => {
                    window.location.href = `/edit_class.html?class_id=${encodeURIComponent(cls.id)}`;
                });
                
                classSearchResults.appendChild(li);
            });

        } catch (error) {
            console.error('Error during class search:', error);
            classSearchResults.innerHTML = `<li style="color: red;">${error.message}</li>`;
        }
    }

    addNewClassButton.addEventListener('click', () => {
        window.location.href = '/add_new_class.html';
    });

    // Handle search results display and clear functionality
    setupSearch('courseSearchInput', 'courseSearchResults', 'courseSearchClear');
    setupSearch('classSearchInput', 'classSearchResults', 'classSearchClear');
  
    // Close results when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('#course-search-container') && 
            !e.target.closest('#class-search-container')) {
            hideAllResults();
        }
    });
});

function setupSearch(inputId, resultsId, clearBtnId) {
    const input = document.getElementById(inputId);
    const results = document.getElementById(resultsId);
    const clearBtn = document.getElementById(clearBtnId);
  
    // Show clear button and results when input has content
    input.addEventListener('input', function() {
        if (this.value) {
            clearBtn.classList.add('visible');
            results.style.display = 'block';
        } else {
            clearBtn.classList.remove('visible');
            results.style.display = 'none';
        }
    });
  
    // Clear button functionality
    clearBtn.addEventListener('click', function() {
        input.value = '';
        results.style.display = 'none';
        clearBtn.classList.remove('visible');
        input.focus();
    });
}

function hideAllResults() {
    // Hide all search results and clear buttons
    const results = document.querySelectorAll('#courseSearchResults, #classSearchResults');
    const clearBtns = document.querySelectorAll('.search-clear-btn');
  
    results.forEach(el => el.style.display = 'none');
    clearBtns.forEach(btn => btn.classList.remove('visible'));
}

// This block of code is redundant with the setupSearch function and can be removed
// document.addEventListener('DOMContentLoaded', function() {
//     const courseInput = document.getElementById('courseSearchInput');
//     const classInput = document.getElementById('classSearchInput');
//     const courseResults = document.getElementById('courseSearchResults');
//     const classResults = document.getElementById('classSearchResults');
//     const courseClear = document.getElementById('courseSearchClear');
//     const classClear = document.getElementById('classSearchClear');
    
//     // Show/hide search results based on input
//     courseInput.addEventListener('input', function() {
//         if (this.value) {
//             courseResults.style.display = 'block';
//             courseClear.classList.add('visible');
//         } else {
//             courseResults.style.display = 'none';
//             courseClear.classList.remove('visible');
//         }
//     });
    
//     classInput.addEventListener('input', function() {
//         if (this.value) {
//             classResults.style.display = 'block';
//             classClear.classList.add('visible');
//         } else {
//             classResults.style.display = 'none';
//             classClear.classList.remove('visible');
//         }
//     });
    
//     // Clear buttons functionality
//     courseClear.addEventListener('click', () => {
//         courseInput.value = '';
//         courseResults.style.display = 'none';
//         courseClear.classList.remove('visible');
//     });
    
//     classClear.addEventListener('click', () => {
//         classInput.value = '';
//         classResults.style.display = 'none';
//         classClear.classList.remove('visible');
//     });
    
//     // Close results when clicking outside
//     document.addEventListener('click', function(e) {
//         if (!e.target.closest('#course-search-container')) {
//             courseResults.style.display = 'none';
//             courseClear.classList.remove('visible');
//         }
        
//         if (!e.target.closest('#class-search-container')) {
//             classResults.style.display = 'none';
//             classClear.classList.remove('visible');
//         }
//     });
// });
