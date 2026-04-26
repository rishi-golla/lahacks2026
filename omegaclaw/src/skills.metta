; OmegaClaw skill surface for remote Agentverse-backed skills.
; Tutorial 03/06 pattern:
;   - one descriptive line in getSkills so LLM knows the skill exists
;   - one-line skill implementation delegating to Python bridge

(= (getSkills)
   (list
      "- Identify a visible badge wearer and return short professional context: (identify-person name_in_quotes organization_in_quotes title_in_quotes)"
      "- Search the web and return concise results: (google-search query_in_quotes)"
      "- Create or list calendar events: (google-calendar command_in_quotes datetime_in_quotes details_in_quotes)"
      "- Draft or send email when explicitly requested: (gmail command_in_quotes recipient_in_quotes subject_in_quotes body_in_quotes)"
      "- Search for a person or prospect profile across sources: (people-search-agent query_in_quotes)"
      "- Send or draft mail through a dedicated mail agent: (mail-sending-agent command_in_quotes recipient_in_quotes subject_in_quotes body_in_quotes)"
      "- Schedule a task or event with a planning agent: (task-scheduling-agent command_in_quotes datetime_in_quotes details_in_quotes)"
      "- Capture a reminder for a later time: (reminder-agent command_in_quotes datetime_in_quotes details_in_quotes)"
      "- Research or prepare a purchase workflow: (purchase-agent command_in_quotes item_in_quotes quantity_in_quotes)"))

; Flagship skill (NOW)
(= (identify-person $name $organization $title)
   (py-call (agentverse_bridge.invoke_identify_person $name $organization $title)))

; Future skills (LATER scaffolding)
(= (google-search $query)
   (py-call (agentverse_bridge.invoke_google_search $query)))

(= (google-calendar $command $datetime $details)
   (py-call (agentverse_bridge.invoke_google_calendar $command $datetime $details)))

(= (gmail $command $recipient $subject $body)
   (py-call (agentverse_bridge.invoke_gmail $command $recipient $subject $body)))

(= (people-search-agent $query)
   (py-call (agentverse_bridge.invoke_people_search_agent $query)))

(= (mail-sending-agent $command $recipient $subject $body)
   (py-call (agentverse_bridge.invoke_mail_sending_agent $command $recipient $subject $body)))

(= (task-scheduling-agent $command $datetime $details)
   (py-call (agentverse_bridge.invoke_task_scheduling_agent $command $datetime $details)))

(= (reminder-agent $command $datetime $details)
   (py-call (agentverse_bridge.invoke_reminder_agent $command $datetime $details)))

(= (purchase-agent $command $item $quantity)
   (py-call (agentverse_bridge.invoke_purchase_agent $command $item $quantity)))
