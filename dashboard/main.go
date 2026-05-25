package main

import (
	"database/sql"
	"fmt"
	"os"
	"strings"

	"github.com/charmbracelet/bubbles/table"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	_ "github.com/lib/pq"
)

type dashboardData struct {
	Overview      []string
	Queue         []table.Row
	Applied       []table.Row
	ScraperStatus []table.Row
	Settings      []string
	Error          string
}

type model struct {
	screen int
	data   dashboardData
}

var screens = []string{"Overview", "Job Queue", "Applied Log", "Scraper Status", "Settings"}

var (
	activeTab = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("15")).
			Background(lipgloss.Color("27")).
			Padding(0, 1)
	inactiveTab = lipgloss.NewStyle().
			Foreground(lipgloss.Color("245")).
			Padding(0, 1)
	panel = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(lipgloss.Color("240")).
		Padding(1, 2)
)

func main() {
	p := tea.NewProgram(model{data: loadData()})
	if _, err := p.Run(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}

func (m model) Init() tea.Cmd {
	return nil
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "q", "ctrl+c":
			return m, tea.Quit
		case "right", "tab", "l":
			m.screen = (m.screen + 1) % len(screens)
		case "left", "shift+tab", "h":
			m.screen--
			if m.screen < 0 {
				m.screen = len(screens) - 1
			}
		case "r":
			m.data = loadData()
		}
	}
	return m, nil
}

func (m model) View() string {
	var tabs []string
	for i, name := range screens {
		if i == m.screen {
			tabs = append(tabs, activeTab.Render(name))
		} else {
			tabs = append(tabs, inactiveTab.Render(name))
		}
	}

	body := ""
	switch screens[m.screen] {
	case "Overview":
		body = strings.Join(m.data.Overview, "\n")
	case "Job Queue":
		body = renderTable([]table.Column{
			{Title: "Grade", Width: 8},
			{Title: "Score", Width: 8},
			{Title: "Company", Width: 22},
			{Title: "Role", Width: 36},
			{Title: "Platform", Width: 12},
		}, m.data.Queue)
	case "Applied Log":
		body = renderTable([]table.Column{
			{Title: "Status", Width: 12},
			{Title: "Company", Width: 22},
			{Title: "Role", Width: 36},
			{Title: "When", Width: 18},
		}, m.data.Applied)
	case "Scraper Status":
		body = renderTable([]table.Column{
			{Title: "Platform", Width: 14},
			{Title: "Role", Width: 24},
			{Title: "Found", Width: 8},
			{Title: "Inserted", Width: 10},
			{Title: "Status", Width: 12},
		}, m.data.ScraperStatus)
	case "Settings":
		body = strings.Join(m.data.Settings, "\n")
	}

	if m.data.Error != "" {
		body += "\n\nDatabase note: " + m.data.Error
	}
	return strings.Join(tabs, " ") + "\n\n" + panel.Width(104).Render(body) + "\n\nq quit | arrows switch | r refresh\n"
}

func renderTable(columns []table.Column, rows []table.Row) string {
	t := table.New(table.WithColumns(columns), table.WithRows(rows), table.WithHeight(14))
	t.SetStyles(table.DefaultStyles())
	return t.View()
}

func loadData() dashboardData {
	data := dashboardData{
		Overview: []string{
			"Total scraped today: 0",
			"Matched today: 0",
			"Applied today: 0",
			"Failed today: 0",
		},
		Settings: []string{
			"Platforms: LinkedIn, Indeed, Naukri, Wellfound",
			"Min match grade: B",
			"Max daily applies: 25",
			"Dry run is controlled by APPLIER_DRY_RUN.",
		},
	}

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgresql://autoapply:autoapply@localhost:5432/autoapply?sslmode=disable"
	}
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		data.Error = err.Error()
		return data
	}
	defer db.Close()

	var scraped, matched, applied, failed int
	_ = db.QueryRow("SELECT COUNT(*) FROM jobs WHERE scraped_at::date = CURRENT_DATE").Scan(&scraped)
	_ = db.QueryRow("SELECT COUNT(*) FROM jobs WHERE updated_at::date = CURRENT_DATE AND match_grade IS NOT NULL").Scan(&matched)
	_ = db.QueryRow("SELECT COUNT(*) FROM applications WHERE applied_at::date = CURRENT_DATE AND status = 'applied'").Scan(&applied)
	_ = db.QueryRow("SELECT COUNT(*) FROM applications WHERE applied_at::date = CURRENT_DATE AND status = 'failed'").Scan(&failed)
	data.Overview = []string{
		fmt.Sprintf("Total scraped today: %d", scraped),
		fmt.Sprintf("Matched today: %d", matched),
		fmt.Sprintf("Applied today: %d", applied),
		fmt.Sprintf("Failed today: %d", failed),
	}

	data.Queue = queryRows(db, `
		SELECT COALESCE(match_grade, '-'), COALESCE(ROUND(composite_score, 2)::text, '-'), company, title, platform
		FROM jobs
		WHERE status = 'queued'
		ORDER BY composite_score DESC NULLS LAST
		LIMIT 20`)

	data.Applied = queryRows(db, `
		SELECT a.status, j.company, j.title, to_char(a.applied_at, 'YYYY-MM-DD HH24:MI')
		FROM applications a
		JOIN jobs j ON j.id = a.job_id
		ORDER BY a.applied_at DESC
		LIMIT 20`)

	data.ScraperStatus = queryRows(db, `
		SELECT platform, COALESCE(role, '-'), jobs_found::text, jobs_inserted::text, status
		FROM scraper_runs
		ORDER BY started_at DESC
		LIMIT 20`)

	return data
}

func queryRows(db *sql.DB, query string) []table.Row {
	rows, err := db.Query(query)
	if err != nil {
		return []table.Row{}
	}
	defer rows.Close()

	columns, err := rows.Columns()
	if err != nil {
		return []table.Row{}
	}
	var result []table.Row
	for rows.Next() {
		values := make([]sql.NullString, len(columns))
		scan := make([]any, len(values))
		for i := range values {
			scan[i] = &values[i]
		}
		if err := rows.Scan(scan...); err != nil {
			continue
		}
		row := table.Row{}
		for _, value := range values {
			if value.Valid {
				row = append(row, value.String)
			} else {
				row = append(row, "")
			}
		}
		result = append(result, row)
	}
	return result
}
