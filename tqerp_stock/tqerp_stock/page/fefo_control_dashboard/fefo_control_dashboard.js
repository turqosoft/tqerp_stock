frappe.pages['fefo-control-dashboard'].on_page_load = function(wrapper) {
    // Redirect to sales dashboard
    window.location.href = '/fefo_control_dashboard';
    
    // Optional: Show loading message while redirecting
    frappe.ui.make_app_page({
        parent: wrapper,
        title: 'FEFO Control Dashboard',
        single_column: true
    });
    
    // Show redirect message
    $(wrapper).html(`
        <div class="text-center" style="padding: 50px;">
            <div class="spinner-border text-primary mb-3" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <h4>Redirecting to FEFO Control Dashboard...</h4>
            <p class="text-muted">If you are not redirected automatically, 
                <a href="/fefo_control_dashboard">click here</a>.
            </p>
        </div>
    `);
};