# strava_integration/views.py

from django.shortcuts import redirect, render, HttpResponseRedirect
from django.http import HttpResponse
import requests
from django.conf import settings
from datetime import datetime
from .models import Activity, Athlete


def login(request):
    # Redirect the user to Strava's authorization endpoint
    authorize_url = (
        f'https://www.strava.com/oauth/authorize?'
        f'client_id={settings.STRAVA_CLIENT_ID}&'
        f'redirect_uri={settings.STRAVA_REDIRECT_URI}&'
        f'response_type=code&'
        f'scope=activity:read_all'
    )
    return redirect(authorize_url)

def auth_callback(request):
    # Retrieve the authorization code from the callback URL
    code = request.GET.get('code')

    # Exchange the code for an access token
    token_data = {
        'client_id': settings.STRAVA_CLIENT_ID,
        'client_secret': settings.STRAVA_CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code'
    }

    response = requests.post('https://www.strava.com/oauth/token', data=token_data)
    token_json = response.json()

    # Store the access token in the session
    request.session['access_token'] = token_json['access_token']
        
    return render(request, 'StravaChallengesApp/confirmationPage.html')
                  
    
                      
def get_stats(request):
    # Check if the user is authenticated
    if 'access_token' not in request.session:
        return redirect('login')

    # Get the user's access token from the session
    access_token = request.session['access_token']

    # Make a request to fetch the user's activities
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://www.strava.com/api/v3/athletes/18772666/stats', headers=headers)

    if response.status_code == 200:
        activities = response.json()
        return HttpResponse(f'Your stats: {activities}')
    else:
        return HttpResponse('Error fetching activities')


    
def main_page(request):
    return render(request, 'StravaChallengesApp/mainPage.html')

def confirmation_page(request):
    return render(request, 'StravaChallengesApp/confirmationPage.html')

def get_athlete_and_stats(request):
    
    # Check if the user is authenticated
    if 'access_token' not in request.session:
        return redirect('login')

    # Get the user's access token from the session
    access_token = request.session['access_token']

            
    # COLLECT DATA FROM API - Make a request to fetch the user's ACTIVITIES
    headers = {'Authorization': f'Bearer {access_token}'}
    
    SINCE_WHAT_DATE = '2023-01-01T00:00:00Z'       

    
    sinceWhenTimestamp = datetime.strptime(SINCE_WHAT_DATE, '%Y-%m-%dT%H:%M:%SZ')
    epochTimeTimestamp = sinceWhenTimestamp.timestamp()
    
    all_activities = []
    pageIndex = 1
    
    while True:
        params = {
        'after': epochTimeTimestamp,
        'per_page': 200,
        'page': pageIndex
    }        
        
        response = requests.get('https://www.strava.com/api/v3/athlete/activities', headers=headers, params=params)
        
        if response.status_code == 200:
            activity = response.json()
            if not activity:
                break
            all_activities.extend(activity)
            pageIndex += 1
        else:
            print(f'Error fetching activities: Status code {response.status_code}, Response content: {response.text}')
            return HttpResponse(f'Error fetching activities: Status code {response.status_code}, Response content: {response.text}')
    
    #creating a dictionary and counter for outdoor activities
    OUTDOOR_ACTIVITIES_TYPES = ["Walk", "Ride", "AlpineSki", "Swim", "Run"]
    activitySummary = dict()
    for acType in OUTDOOR_ACTIVITIES_TYPES:
        activitySummary[acType] = 0
    
    weightTrainingCounter = 0
    
    #going through activities and saving to database
    for outdoorActivity in all_activities:
        activity_type_fetched = outdoorActivity['type']
        activity_distance_fetched = outdoorActivity['distance']
        activity_athlete_fetched  = outdoorActivity['athlete']['id']
        activity_id_fetched = outdoorActivity['id']
        activity_start_date_fetched = outdoorActivity['start_date'][0:10]
        
        try: 
            Activity.objects.get(activity_id = activity_id_fetched)
            
        except:            
            activity_to_be_saved = Activity(activity_athlete = activity_athlete_fetched,
                                            activity_id = activity_id_fetched,
                                            activity_type = activity_type_fetched,
                                            start_date = activity_start_date_fetched,
                                            distance = activity_distance_fetched)
            activity_to_be_saved.save()
        
        if outdoorActivity['type'] in OUTDOOR_ACTIVITIES_TYPES:
            activitySummary[outdoorActivity['type']] += int(outdoorActivity['distance'])
        else:
            weightTrainingCounter += 1     

     
    
     # Make a request to fetch ATHLETE
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://www.strava.com/api/v3/athlete', headers=headers)
    
    if response.status_code == 200:
        athleteData = response.json()        
        global athlete_id_fetched
        athlete_id_fetched = athleteData['id']        
        firstname_fetched = athleteData['firstname']
        lastname_fetched = athleteData['lastname']
        sex_fetched = athleteData['sex']
        photo_medium_url_fetched = athleteData['profile_medium']
        photo_large_url_fetched = athleteData['profile']
        
        totalDistance = sum(activitySummary.values())
        
        # Store Athlete data in database
        try:  
            current_athlete = Athlete.objects.get(athlete_id = athlete_id_fetched) #check if athlete in datasbase positivie = saving activity only
            current_athlete.total_ytd_distance = int(totalDistance/1000)
            current_athlete.ride_ytd_distance = int(activitySummary['Ride']/1000)
            current_athlete.run_ytd_distance = int(activitySummary['Run']/1000)
            current_athlete.walk_ytd_distance = int(activitySummary['Walk']/1000)
            current_athlete.swim_ytd_distance = int(activitySummary['Swim']/1000)
            current_athlete.ski_ytd_distance = int(activitySummary['AlpineSki']/1000)
            current_athlete.save()
            
        except Athlete.DoesNotExist: #athlete not in database - adding athlete
            username_fetched = athleteData['username']
            
            if username_fetched is None: #avoiding None field value
                username_fetched = 'brak'            
            
            athlete_to_be_saved = Athlete(athlete_id = athlete_id_fetched,
                                          username = username_fetched,
                                          firstname = firstname_fetched,
                                          lastname = lastname_fetched,
                                          sex = sex_fetched,
                                          photo_medium_url = photo_medium_url_fetched,
                                          photo_large_url = photo_large_url_fetched,
                                          total_ytd_distance = int(totalDistance/1000),
                                          ride_ytd_distance = int(activitySummary['Ride']/1000),
                                          run_ytd_distance = int(activitySummary['Run']/1000),
                                          walk_ytd_distance = int(activitySummary['Walk']/1000),
                                          swim_ytd_distance = int(activitySummary['Swim']/1000),
                                          ski_ytd_distance = int(activitySummary['AlpineSki']/1000))
            
            athlete_to_be_saved.save()
       
    
    return HttpResponseRedirect('/y5k_results_page')


def y5k_results_page(request):
    athletes = Athlete.objects.order_by('-total_ytd_distance')
    activities = Activity.objects.all()
    athletesList = []
    atheltesDistance = []
    colorsList = []
    colorsList2 = []
    
    try:
        print(athlete_id_fetched, ' to jest athlete id_fetched')
    except Exception as e:
        print('we have a following error', e)
    
    dataSet = Athlete.objects.order_by('-total_ytd_distance')
    for data in dataSet:
        athletesList.append(f"{data.firstname} {data.lastname}")
        atheltesDistance.append(data.total_ytd_distance)
        try:
            if athlete_id_fetched == int(data.athlete_id):
                colorsList.append('red')
            else:
                colorsList.append('orange')
        except:
            colorsList.append('orange')
    print(colorsList)   
    return render(request, 'StravaChallengesApp/y5kResultsPage.html',{
        'athletes': athletes,
        'activities': activities,
        'athleteList': athletesList,
        'athletesDistance': atheltesDistance,
        'colorsList': colorsList
    })