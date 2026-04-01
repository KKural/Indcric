from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from decimal import Decimal, InvalidOperation
from .models import Session, Poll, Vote, RatingPoll, RatingVote, User
from .forms_polls import PollForm


@login_required
def poll_detail_view(request, poll_id):
    poll = get_object_or_404(Poll, id=poll_id)
    user_vote = None
    if request.user.is_authenticated:
        vote = Vote.objects.filter(poll=poll, user=request.user).first()
        if vote:
            user_vote = vote.choice

    if request.method == 'POST':
        if not poll.is_open:
            return HttpResponseForbidden("This poll is closed.")

        choice = request.POST.get('choice')
        if choice in ['yes', 'no']:
            vote, created = Vote.objects.update_or_create(
                poll=poll,
                user=request.user,
                defaults={'choice': choice}
            )
        return redirect('poll_detail', poll_id=poll.id)

    yes_votes = poll.votes.filter(choice='yes').count()
    no_votes = poll.votes.filter(choice='no').count()
    total_votes = yes_votes + no_votes

    context = {
        'poll': poll,
        'yes_votes': yes_votes,
        'no_votes': no_votes,
        'total_votes': total_votes,
        'user_vote': user_vote,
        'poll_url': request.build_absolute_uri(poll.get_absolute_url())
    }
    return render(request, 'cric/pages/poll_detail.html', context)


@login_required
def create_poll_view(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    if hasattr(session, 'poll'):
        return redirect('poll_detail', poll_id=session.poll.id)

    if request.method == 'POST':
        form = PollForm(request.POST)
        if form.is_valid():
            poll = form.save(commit=False)
            poll.session = session
            poll.save()
            return redirect('poll_detail', poll_id=poll.id)
    else:
        form = PollForm()

    context = {
        'form': form,
        'session': session
    }
    return render(request, 'cric/pages/create_poll.html', context)


# ── Rating Poll views ─────────────────────────────────────────────────────────

@login_required
def rating_poll_list_view(request):
    polls = RatingPoll.objects.select_related(
        'player', 'created_by').order_by('-created_at')
    return render(request, 'cric/pages/rating_poll_list.html', {'polls': polls})


@login_required
def rating_poll_detail_view(request, poll_id):
    poll = get_object_or_404(RatingPoll, pk=poll_id)
    existing_vote = RatingVote.objects.filter(
        poll=poll, voter=request.user).first()
    votes_count = poll.votes.count()
    context = {
        'poll': poll,
        'existing_vote': existing_vote,
        'votes_count': votes_count,
    }
    return render(request, 'cric/pages/rating_poll_detail.html', context)


@login_required
def vote_rating_poll_view(request, poll_id):
    poll = get_object_or_404(RatingPoll, pk=poll_id)
    if request.method == 'POST':
        if not poll.is_open:
            messages.error(request, "This rating poll is closed.")
            return redirect('rating_poll_detail', poll_id=poll_id)
        try:
            batting = min(
                max(Decimal(request.POST.get('batting', '5.0')), Decimal('1')), Decimal('10'))
            bowling = min(
                max(Decimal(request.POST.get('bowling', '5.0')), Decimal('1')), Decimal('10'))
            fielding = min(
                max(Decimal(request.POST.get('fielding', '5.0')), Decimal('1')), Decimal('10'))
        except (InvalidOperation, TypeError):
            messages.error(request, "Invalid rating values.")
            return redirect('rating_poll_detail', poll_id=poll_id)
        RatingVote.objects.update_or_create(
            poll=poll, voter=request.user,
            defaults={'batting': batting,
                      'bowling': bowling, 'fielding': fielding}
        )
        messages.success(request, "Your rating has been saved.")
    return redirect('rating_poll_detail', poll_id=poll_id)


@login_required
def close_rating_poll_view(request, poll_id):
    if not request.user.is_staff:
        messages.error(
            request, "You don't have permission to perform this action.")
        return redirect('rating_poll_list')
    poll = get_object_or_404(RatingPoll, pk=poll_id)
    if request.method == 'POST':
        if poll.is_open:
            poll.is_open = False
            poll.save()
            # Calculate averages and update player ratings
            votes = poll.votes.all()
            if votes.exists():
                count = votes.count()
                avg_bat = sum(v.batting for v in votes) / count
                avg_bowl = sum(v.bowling for v in votes) / count
                avg_field = sum(v.fielding for v in votes) / count
                # Round to nearest 0.5
                player = poll.player
                player.batting_rating = round(float(avg_bat) * 2) / 2
                player.bowling_rating = round(float(avg_bowl) * 2) / 2
                player.fielding_rating = round(float(avg_field) * 2) / 2
                player.save()
                messages.success(
                    request, f"Poll closed. Ratings updated: Bat {player.batting_rating}, Bowl {player.bowling_rating}, Field {player.fielding_rating}.")
            else:
                messages.warning(
                    request, "Poll closed with no votes — ratings unchanged.")
        else:
            poll.is_open = True
            poll.save()
            messages.success(request, "Rating poll re-opened.")
    return redirect('rating_poll_detail', poll_id=poll_id)


@login_required
def create_rating_poll_view(request, user_id):
    if not request.user.is_staff:
        messages.error(
            request, "You don't have permission to perform this action.")
        return redirect('manage-users')
    player = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        poll = RatingPoll.objects.create(
            player=player, created_by=request.user)
        messages.success(
            request, f"Rating poll created for {player.get_full_name() or player.username}.")
        return redirect('rating_poll_detail', poll_id=poll.id)
    return redirect('manage-users')
