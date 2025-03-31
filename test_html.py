import streamlit as st

st.title("HTML Rendering Test")

# Test HTML rendering
html_content = """
<div>
    <h3>Test Fixtures</h3>
    <table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd;">
        <thead>
            <tr style="background-color: #38003c; color: white;">
                <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Home Team</th>
                <th style="padding: 8px; text-align: center; border: 1px solid #ddd;">vs</th>
                <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Away Team</th>
                <th style="padding: 8px; text-align: center; border: 1px solid #ddd;">Date</th>
            </tr>
        </thead>
        <tbody>
            <tr style="border: 1px solid #ddd;">
                <td style="padding: 8px; border: 1px solid #ddd;">
                    <div style="display: flex; align-items: center;">
                        <img src="https://media.api-sports.io/football/teams/39.png" 
                             alt="Team 1" style="width: 24px; height: 24px; margin-right: 8px;">
                        Team 1
                    </div>
                </td>
                <td style="padding: 8px; text-align: center; border: 1px solid #ddd;">vs</td>
                <td style="padding: 8px; border: 1px solid #ddd;">
                    <div style="display: flex; align-items: center;">
                        <img src="https://media.api-sports.io/football/teams/40.png" 
                             alt="Team 2" style="width: 24px; height: 24px; margin-right: 8px;">
                        Team 2
                    </div>
                </td>
                <td style="padding: 8px; text-align: center; border: 1px solid #ddd;">01/01/2023</td>
            </tr>
        </tbody>
    </table>
</div>
"""

# Render HTML with unsafe_allow_html=True
st.markdown(html_content, unsafe_allow_html=True)

st.write("If the HTML rendered correctly, you should see a table above with team names and images.") 