// js/footer.js

document.addEventListener('DOMContentLoaded', () => {
    const createFooter = () => {
        const footerElement = document.createElement('footer');
        footerElement.className = 'footer'; // Apply the existing footer styles

        // Add footer content
        // IMPORTANT: For external links, use target="_blank" rel="noopener noreferrer"
        // This opens the link in a new tab and enhances security.
        footerElement.innerHTML = `
            <div class="footer-links">
                <a href="index.html">Home</a>
                <a href="https://byuh.edu" target="_blank" rel="noopener noreferrer">BYU-Hawaii</a>
                <a href="https://holokai.m.byuh.edu/p/build-your-holokai" target="_blank" rel="noopener noreferrer">Build Your Holokai</a>
                <a href="https://advising.byuh.edu/academic-advisors" target="_blank" rel="noopener noreferrer">Academic Advising</a>
                <a href="https://catalog.byuh.edu/courses" target="_blank" rel="noopener noreferrer">Courses</a>
            </div>
            <p>&copy; ${new Date().getFullYear()} Brigham Young University-Hawaii. All rights reserved.</p>
        `;

        // Append the footer to the body
        document.body.appendChild(footerElement);
    };

    // Call the function to create the footer
    createFooter();
});
