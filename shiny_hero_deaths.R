library(shiny)
library(plotly)
library(tidyverse)
library(here)

# load data
hero_died_all <- read_csv(here("hero_died_all.csv"))
building_position_all <- read_csv(here("building_position_all.csv"))
map_axis_scaling_df <- read_csv(here("map_axis_scaling_df.csv"))

# data cleanup
# define game phases
# 1) lvl 1 - before lvl 10
# 2) before lvl 16
# 3) before lvl 20
# 4) one at lvl 20 - both lvl 20
# 5) lvl 20 +
hero_died_all <- hero_died_all %>%
  filter(died_gameloop != 0,
         !is.na(m_killerUnitTagIndex)) %>%
  rowwise() %>%
  mutate(phase = ifelse(max(team0_lvl, team1_lvl) < 10, "1 - pre 10",
                        ifelse(max(team0_lvl, team1_lvl) < 16, "2 - pre 16",
                               ifelse(max(team0_lvl, team1_lvl) < 20, "3 - pre 20", 
                                      ifelse(min(team0_lvl, team1_lvl) < 20, "4 - one 20", "5 - 20+"))))
  ) %>%
  ungroup()

# make stored lists into lists
csv_string_to_list <- function(x){
  x <- as.list(strsplit(x, ", ")[[1]])
  x <- str_replace_all(x, "[[:punct:]]", "")
  return(x)
}

csv_cols = c("near_friend_ls_hero", "near_enemy_ls_hero", 
             "near_friend_ls_player","near_enemy_ls_player","all_players")

temp_df <- data.frame(matrix(ncol = 5, nrow = 0))
colnames(temp_df) = paste0(csv_cols,"_rlist")

for (row_i in 1:nrow(hero_died_all)){
  for (col_i in csv_cols){
    temp_df[row_i,paste0(col_i,"_rlist")][[1]] <- list(csv_string_to_list(toString(hero_died_all[row_i,col_i])))
  }
}

hero_died_all <- cbind(hero_died_all,temp_df)

# left or right team won
hero_died_all <- hero_died_all %>%
  mutate(win_team = ifelse((m_teamId == 0 & m_result == 1)|
                             (m_teamId == 1 & m_result == 2), "left", "right"))

# github_image_link = "https://github.com/kevinchtsang/heroes-of-the-storm-analysis/blob/main/Maps/"

# colour scales
hot_colors <- list(c(0,'rgba(0,0,0,0)'),c(0.01, "yellow"), c(1, "red"))
cool_colors <- list(c(0,'rgba(0,0,0,0)'),c(0.01, "green"), c(1, "blue"))
custom_colors <- list(hot_colors = hot_colors, 
                      cool_colors = cool_colors)

# optional filters
conditional <- function(condition, success) {
  if (condition) success else TRUE
}

ui <- fluidPage(
  headerPanel('Where Heroes Died'),
  sidebarPanel(
    selectInput('map_name','Map name', sort(unique(hero_died_all$map))),
    selectInput('players', 'Players (leave empty for all)', sort(unique(hero_died_all$m_name)), multiple = TRUE),
    checkboxGroupInput('game_phase', 'Game phase', sort(unique(hero_died_all$phase)), 
                 unique(hero_died_all$phase)),
    radioButtons('win_team', "Which side was the winning team", c("left", "right", "both"), "both"),
    radioButtons('kill_die', "Look at kills, deaths, or both", c("kills", "deaths", "both", "played_game"), "played_game"),
    sliderInput('bin_width', "Bin width", 2, 20, 5),
    radioButtons('plot_type', "Plot type", c("heatmap", "scatter")),
    radioButtons('colors', "Choose colour scale", names(custom_colors))
  ),
  mainPanel(
    plotlyOutput('plot_hero_died'),
    textOutput('map_description'),
    tableOutput('analysis_summary')
    # plotlyOutput('plot_buildings')
  )
)

server <- function(input, output, session) {
  # games_with_players <- reactive({
  #   hero_died_all %>% 
  #     filter(map == input$map_name,
  #            m_name %in% input$players) %>%
  #     select(replay_file)
  # })
  
#   plot_died_df <- reactive({
#     hero_died_all %>%
#       filter(map == input$map_name,
#              phase %in% input$game_phase, 
#              conditional(input$kill_die == "kills", 
#                          conditional(length(input$players) > 0, (m_name %in% near_enemy_ls_player
# ))),
#              conditional(input$kill_die == "deaths", 
#                          conditional(length(input$players) > 0, (m_name %in% input$players))),
#              conditional(input$kill_die == "both", 
#                          conditional(length(input$players) > 0, (m_name %in% input$players)))
#              
#       )
#   })
  
  # update inputs
  observe(updateSelectInput(session, "players",
                            choices = sort(unique(
                              hero_died_all[hero_died_all$map == input$map_name,]$m_name))))
  
  # create df
  plot_died_df_filter_map_phase <- reactive({
    hero_died_all %>%
      filter(map == input$map_name,
             phase %in% input$game_phase)
  })
  plot_died_df_filter_players <- reactive({
    plot_died_df_filter_map_phase() %>%
      # filter(conditional(length(input$players) > 0, all_players_rlist %in% input$players))
      filter(conditional(length(input$players) > 0, grepl(paste(input$players, collapse = "|"), 
                                                            all_players)))
    
  })
  plot_died_df_filter_team <- reactive({
    plot_died_df_filter_players() %>%
      filter(conditional(input$win_team %in% c("left", "right"), win_team == input$win_team))
  })
  plot_died_df <- reactive({
    plot_died_df_filter_team() %>%
      filter(conditional(input$kill_die == "kills", grepl(paste(input$players, collapse = "|"), 
                                                          near_enemy_ls_player)),
             conditional(input$kill_die == "deaths", m_name %in% input$players),
             conditional(input$kill_die == "both", grepl(paste(input$players, collapse = "|"), 
                                                         near_enemy_ls_player) | 
                           (m_name %in% input$players)),
             conditional(input$kill_die == "played_game", TRUE))
  })
  
  plot_building_df <- reactive({
    building_position_all %>%
      filter(map_name == input$map_name)
  })
  
  # image_filename <- reactive({paste0(github_image_link, 
  #                                    str_replace(input$map_name, " ", "%20"), 
  #                                    ".jpeg?raw=true")})
  image_filename <- reactive({here(paste0("Maps/",input$map_name,".jpeg"))})
  
  map_details <- reactive({
    map_axis_scaling_df %>% 
      filter(map_name == input$map_name)
  })
  
  color_list <- reactive({custom_colors[[input$colors]]})
  
  analysis_summary_df <- reactive({
    plot_died_df() %>% 
      # group_by(map, phase, m_name, replay_files) %>%
      # ungroup() %>%
      group_by(map, m_name) %>%
      mutate(n_games = n_distinct(replay_file)) %>%
      ungroup() %>%
      group_by(map, phase, m_name, n_games, replay_file) %>%
      mutate(n_deaths = n()) %>%
      ungroup() %>%
      group_by(map, phase, m_name, n_games) %>%
      summarise(
        avg_deaths = mean(n_deaths),
        avg_near_friend = mean(near_friend),
        avg_near_enemy = mean(near_enemy)) %>%
      ungroup()
  })
  
  output$plot_hero_died <- renderPlotly(
    plot1 <- plot_ly(
      plot_died_df(),
      x = ~died_m_x,
      y = ~died_m_y
      # mode = "marker",
      # marker = list(color="RebeccaPurple")
      ) %>%
      add_histogram2d(
        # nbinsx = as.integer((max(plot_died_df()$died_m_x) - min(plot_died_df()$died_m_x)) / input$bin_width),
        # nbinsy = as.integer((max(plot_died_df()$died_m_y) - min(plot_died_df()$died_m_y)) / input$bin_width),
        # nbinsx = as.integer((max(plot_building_df()$x) - min(plot_building_df()$y)) / input$bin_width),
        # nbinsy = as.integer((max(plot_building_df()$x) - min(plot_building_df()$y)) / input$bin_width),
        xbins = list(size = input$bin_width),
        ybins = list(size = input$bin_width),
        opacity = 0.5,
        colorscale = color_list()
        ) %>% 
      layout(
        images = list(
            list(
              source = base64enc::dataURI(file = image_filename()),
              xref    = "x",
              yref    = "y",
              x       = map_details()$xmax / 2 + map_details()$xaxes_translate,
              y       = map_details()$ymax / 2 + map_details()$yaxes_translate,
              xanchor = "center", #"left",
              yanchor = "middle", #"bottom",
              sizex   = map_details()$xmax * map_details()$xaxes_scale, # length of x
              sizey   = map_details()$ymax * map_details()$yaxes_scale , # length of y
              sizing  = "stretch",
              opacity = 1,
              layer   = "below")
          ),
        xaxis = list(title = "x",
                     range = c(0, map_details()$xmax)),
        yaxis = list(title = "y",
                     range = c(0, map_details()$ymax))
        )
  )
  
  # output$plot_buildings <- renderPlotly(
  #   plot1 <- plot_ly(
  #     plot_building_df(),
  #     x = ~x,
  #     y = ~y,
  #     type = "scatter") %>%
  #     layout(
  #       images = list(
  #         list(
  #           source = base64enc::dataURI(file = image_filename()),
  #           xref    = "x",
  #           yref    = "y",
  #           x       = map_details()$xmax / 2 + map_details()$xaxes_translate,
  #           y       = map_details()$ymax / 2 + map_details()$yaxes_translate,
  #           xanchor = "center", #"left",
  #           yanchor = "middle", #"bottom",
  #           sizex   = map_details()$xmax * map_details()$xaxes_scale, # length of x
  #           sizey   = map_details()$ymax * map_details()$yaxes_scale , # length of y
  #           sizing  = "stretch",
  #           opacity = 1,
  #           layer   = "below")
  #       )
  #     )
  # )
  output$map_description <- renderText({ 
    paste0("Games analysed: ", length(unique(plot_died_df()$replay_file)), 
           "\nReplay files: ", paste(unique(plot_died_df()$replay_file),collapse = ",\n"))
  })
  
  output$analysis_summary <- renderTable(analysis_summary_df())
}

shinyApp(ui,server)