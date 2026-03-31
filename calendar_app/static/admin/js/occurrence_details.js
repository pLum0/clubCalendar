document.addEventListener('DOMContentLoaded', function() {
    const eventSelect = document.getElementById('id_event');
    const occurrenceSelect = document.getElementById('id_occurrence_select');
    const occurrenceDateInput = document.getElementById('id_occurrence_date');
    
    if (!eventSelect || !occurrenceSelect) return;
    
    function fetchOccurrences() {
        const eventId = eventSelect.value;
        if (!eventId) {
            occurrenceSelect.innerHTML = '<option value="">-- Select an event first --</option>';
            return;
        }
        
        occurrenceSelect.innerHTML = '<option value="">Loading...</option>';
        
        const basePath = window.location.pathname.split('/').slice(0, 3).join('/');
        fetch(`${basePath}/get-occurrences/${eventId}/`)
            .then(response => response.json())
            .then(data => {
                occurrenceSelect.innerHTML = '<option value="">-- Enter date manually or select from list --</option>';
                if (data.occurrences && data.occurrences.length > 0) {
                    data.occurrences.forEach(function(occ) {
                        const option = document.createElement('option');
                        option.value = occ.date;
                        option.textContent = occ.label;
                        occurrenceSelect.appendChild(option);
                    });
                    occurrenceSelect.parentElement.style.display = '';
                } else {
                    const option = document.createElement('option');
                    option.value = '';
                    option.textContent = 'No upcoming occurrences (not a recurring event)';
                    occurrenceSelect.appendChild(option);
                }
            })
            .catch(function() {
                occurrenceSelect.innerHTML = '<option value="">Error loading occurrences</option>';
            });
    }
    
    occurrenceSelect.addEventListener('change', function() {
        if (this.value) {
            occurrenceDateInput.value = this.value;
        }
    });
    
    eventSelect.addEventListener('change', fetchOccurrences);
    
    if (eventSelect.value) {
        fetchOccurrences();
    } else {
        occurrenceSelect.innerHTML = '<option value="">-- Select an event first --</option>';
    }
});
